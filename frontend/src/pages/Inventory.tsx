import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, Upload, FileDown, Plus, Loader2, X, RefreshCw } from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { useInventory } from '../hooks/useInventory';
import api from '../services/api';
import { SUPPLY_CATEGORY_LABELS } from '../utils/constants';
import InventoryAlertCard from '../components/inventory/InventoryAlertCard';
import InventoryToolbar, {
  type InventoryFilters,
} from '../components/inventory/InventoryToolbar';
import InventoryTable, {
  type InventoryRow,
} from '../components/inventory/InventoryTable';
import { classifyStatus } from '../components/inventory/InventoryStatusBadge';
import { adminSeverityService, type SupplyNormCell } from '../services/adminSeverityService';
import { useDiseaseOptions } from '../hooks/useForecastAnalysis';

const PAGE_SIZE = 10;

/** Module 6 — Quản lý Vật tư Y tế & Kho vận */
export default function Inventory() {
  const { setPageTitle } = useUIStore();

  useEffect(() => {
    setPageTitle('Quản lý vật tư y tế & Kho vận');
  }, [setPageTitle]);

  return <InventoryContent />;
}

/**
 * Main inventory content (extracted to component for cleaner code)
 */
function InventoryContent() {
  const [filters, setFilters] = useState<InventoryFilters>({
    search: '',
    category: 'all',
    status: 'all',
    disease: '',
    level: 'all',
  });
  const [page, setPage] = useState(1);
  const [normMap, setNormMap] = useState<Map<string, SupplyNormCell>>(new Map());
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    imported: number;
    updated: number;
    skipped: number;
    errors: { row: number; reason: string }[];
    truncated: boolean;
  } | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingItem, setEditingItem] = useState<InventoryRow | null>(null);
  const [deletingItem, setDeletingItem] = useState<InventoryRow | null>(null);
  const [syncingSafety, setSyncingSafety] = useState(false);
  const [syncResult, setSyncResult] = useState<{
    forecast_month: string;
    buffer_rate: number;
    updated: number;
    skipped: number;
    message: string;
  } | null>(null);

  const { data: inventory = [], isLoading, refetch } = useInventory({ limit: 2000 });

  // Bệnh dùng để tra định mức = NHÓM ICD (khớp icd_code đã lưu ở
  // severity_rates/disease_supply_norms — 2 bảng này đã chuyển sang cấp
  // nhóm từ trước, không còn theo 4 mã lẻ J20/J06/J02/J01 nữa).
  const { data: diseaseGroups = [] } = useDiseaseOptions();
  const diseases = useMemo(
    () => [
      { value: '', label: 'Tất cả' },
      ...diseaseGroups.map((g) => ({ value: g.key, label: `${g.label} (${g.key})` })),
    ],
    [diseaseGroups],
  );

  // Fetch norm matrix khi đổi bệnh
  useEffect(() => {
    if (!filters.disease) {
      setNormMap(new Map());
      return;
    }
    let cancelled = false;
    adminSeverityService.getNormMatrix(filters.disease).then((data) => {
      if (cancelled) return;
      const map = new Map<string, SupplyNormCell>();
      data.supplies.forEach((s) => {
        // Key bằng supply_code để ghép với bảng kho
        map.set(s.supply_code, s);
      });
      setNormMap(map);
    }).catch(() => {
      if (!cancelled) setNormMap(new Map());
    });
    return () => { cancelled = true; };
  }, [filters.disease]);

  // Map raw inventory → flat row dùng cho bảng
  const allRows: InventoryRow[] = useMemo(() => {
    return inventory.map((item: any, idx: number) => {
      const supply = item.supply ?? {};
      const code =
        supply.supply_code ??
        buildSupplyCode(supply.category, item.supply_id ?? item.id ?? idx);
      const categoryLabel =
        supply.group_name ??
        SUPPLY_CATEGORY_LABELS[supply.category] ??
        supply.category ??
        '—';
      const supplyName = supply.ten_hoat_chat ?? supply.name ?? '—';
      // Ghép dữ liệu định mức nếu có
      const norm = normMap.get(code);
      
      return {
        id: item.id,
        code,
        name: supplyName,
        category: categoryLabel,
        unit: supply.unit ?? '—',
        currentStock: item.current_stock ?? 0,
        safetyStock: item.safety_stock ?? 0,
        mild: norm?.mild,
        moderate: norm?.moderate,
        severe: norm?.severe,
      };
    });
  }, [inventory, normMap]);

  // Lấy danh sách category xuất hiện trong dữ liệu
  const categoryOptions = useMemo(() => {
    const unique = new Set<string>();
    inventory.forEach((it: any) => {
      const cat = it.supply?.group_name ?? it.supply?.category;
      if (cat) unique.add(cat);
    });
    return Array.from(unique).map((key) => ({
      key,
      label: SUPPLY_CATEGORY_LABELS[key] ?? key,
    }));
  }, [inventory]);

  // Áp filter
  const filtered = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return allRows.filter((r) => {
      if (q && !`${r.code} ${r.name}`.toLowerCase().includes(q)) return false;
      if (filters.category !== 'all') {
        const label = SUPPLY_CATEGORY_LABELS[filters.category] ?? filters.category;
        if (r.category !== label) return false;
      }
      if (filters.status !== 'all') {
        const status = classifyStatus(r.currentStock, r.safetyStock);
        if (status !== filters.status) return false;
      }
      // Lọc theo cấp độ: chỉ hiển thị thuốc có định mức > 0 ở cấp độ đang chọn
      if (filters.level !== 'all') {
        const val = r[filters.level] ?? 0;
        if (val <= 0) return false;
      }
      return true;
    });
  }, [allRows, filters]);

  // Đếm số mục cảnh báo (low + critical)
  const alertCount = useMemo(() => {
    return allRows.reduce((acc, r) => {
      const s = classifyStatus(r.currentStock, r.safetyStock);
      return s === 'normal' ? acc : acc + 1;
    }, 0);
  }, [allRows]);

  // Paginate
  const paged = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  // Reset page khi filter đổi
  useEffect(() => {
    setPage(1);
  }, [filters.search, filters.category, filters.status, filters.disease, filters.level]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleDownloadTemplate = () => {
    window.open(`${api.defaults.baseURL}/inventory/template`, '_blank');
  };

  const handleExportExcel = async () => {
    if (exporting) return;
    try {
      setExporting(true);
      const res = await api.get('/inventory/export', { responseType: 'blob' });
      const blob = new Blob([res.data], {
        type:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `inventory_${new Date()
        .toISOString()
        .replace(/[-:T]/g, '')
        .slice(0, 14)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert('Không thể xuất file Excel. Vui lòng thử lại.');
    } finally {
      setExporting(false);
    }
  };

  const handleImportFile = async (file: File) => {
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/inventory/import', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });
      const d = res.data ?? {};
      setImportResult({
        imported: d.imported ?? 0,
        updated: d.updated ?? 0,
        skipped: d.skipped ?? 0,
        errors: d.errors ?? [],
        truncated: !!d.errors_truncated,
      });
      refetch();
    } catch (err: any) {
      alert(
        'Lỗi import: ' +
          (err?.response?.data?.detail || err.message || 'không xác định'),
      );
    } finally {
      setImporting(false);
    }
  };

  const handleEdit = (row: InventoryRow) => {
    setEditingItem(row);
  };

  const handleDelete = (row: InventoryRow) => {
    setDeletingItem(row);
  };

  const confirmDelete = async () => {
    if (!deletingItem) return;
    try {
      await api.delete(`/inventory/${deletingItem.id}`);
      refetch();
      setDeletingItem(null);
    } catch (err: any) {
      alert(
        'Lỗi xoá vật tư: ' +
          (err?.response?.data?.detail || err.message || 'không xác định'),
      );
    }
  };

  const handleSyncSafetyStock = async () => {
    if (syncingSafety) return;
    const confirm = window.confirm(
      'Cập nhật ngưỡng an toàn cho tất cả vật tư từ kết quả dự báo gần nhất?\n\n' +
      'Hành động này sẽ ghi đè các giá trị ngưỡng AT hiện tại.'
    );
    if (!confirm) return;

    try {
      setSyncingSafety(true);
      const res = await api.post('/inventory/sync-safety-stock', null, {
        params: {
          buffer_rate: 15,
        },
      });
      setSyncResult(res.data);
      refetch();
    } catch (err: any) {
      alert(
        'Lỗi cập nhật ngưỡng AT: ' +
          (err?.response?.data?.detail || err.message || 'không xác định'),
      );
    } finally {
      setSyncingSafety(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">
            Quản lý vật tư y tế & Kho vận
          </h2>
          <p className="text-sm text-neutral-500 mt-1">
            Tổng quan tình trạng kho, cảnh báo vật tư và đơn hàng chờ nhập.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleImportFile(f);
              if (e.target) e.target.value = '';
            }}
          />
          <ActionButton
            variant="outline"
            icon={
              syncingSafety ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )
            }
            onClick={handleSyncSafetyStock}
          >
            {syncingSafety ? 'Đang cập nhật...' : 'Cập nhật ngưỡng AT từ dự báo'}
          </ActionButton>
          <ActionButton
            variant="outline"
            icon={
              exporting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )
            }
            onClick={handleExportExcel}
          >
            {exporting ? 'Đang xuất...' : 'Xuất báo cáo tồn kho'}
          </ActionButton>
          <ActionButton
            variant="outline"
            icon={<FileDown className="w-4 h-4" />}
            onClick={handleDownloadTemplate}
          >
            Tải template mẫu
          </ActionButton>
          <ActionButton
            variant="outline"
            icon={
              importing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Upload className="w-4 h-4" />
              )
            }
            onClick={() => fileInputRef.current?.click()}
          >
            {importing ? 'Đang import...' : 'Import tồn kho đầu kỳ'}
          </ActionButton>
          <ActionButton
            variant="primary"
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setShowAddForm(true)}
          >
            Thêm vật tư mới
          </ActionButton>
        </div>
      </div>

      {/* Alert summary */}
      <InventoryAlertCard count={alertCount} />

      {/* Inventory table card */}
      <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
        <InventoryToolbar
          filters={filters}
          onChange={setFilters}
          categories={categoryOptions}
          diseases={diseases}
        />
        <InventoryTable
          rows={paged}
          isLoading={isLoading}
          total={filtered.length}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          onEdit={handleEdit}
          onDelete={handleDelete}
          showSeverity={normMap.size > 0}
          level={filters.level}
        />
      </div>

      {/* Footer attribution */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-400 pt-2 border-t border-neutral-100">
        <span>
          © 2026 MedForecast AI. Vận hành bởi Phòng Công nghệ Thông tin Y tế.
        </span>
        <div className="flex items-center gap-4">
          <a className="hover:text-neutral-600" href="#">Điều khoản</a>
          <a className="hover:text-neutral-600" href="#">Bảo mật</a>
          <a className="hover:text-neutral-600" href="#">Hướng dẫn sử dụng</a>
        </div>
      </div>

      {/* Add supply form */}
      {showAddForm && (
        <AddSupplyDialog
          onClose={() => setShowAddForm(false)}
          onSaved={() => {
            setShowAddForm(false);
            refetch();
          }}
        />
      )}

      {/* Edit supply form */}
      {editingItem && (
        <EditSupplyDialog
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onSaved={() => {
            setEditingItem(null);
            refetch();
          }}
        />
      )}

      {/* Delete confirmation dialog */}
      {deletingItem && (
        <ConfirmDeleteDialog
          item={deletingItem}
          onClose={() => setDeletingItem(null)}
          onConfirm={confirmDelete}
        />
      )}

      {/* Import result modal */}
      {importResult && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-2xl shadow-xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Kết quả import tồn kho</h3>
              <button
                onClick={() => setImportResult(null)}
                className="p-1 rounded hover:bg-neutral-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3">
                <p className="text-[11px] uppercase font-semibold text-emerald-700">Thêm mới</p>
                <p className="text-2xl font-extrabold text-emerald-700 mt-1 tabular-nums">
                  {importResult.imported.toLocaleString('vi-VN')}
                </p>
              </div>
              <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
                <p className="text-[11px] uppercase font-semibold text-blue-700">Cập nhật</p>
                <p className="text-2xl font-extrabold text-blue-700 mt-1 tabular-nums">
                  {importResult.updated.toLocaleString('vi-VN')}
                </p>
              </div>
              <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
                <p className="text-[11px] uppercase font-semibold text-amber-700">Bỏ qua</p>
                <p className="text-2xl font-extrabold text-amber-700 mt-1 tabular-nums">
                  {importResult.skipped.toLocaleString('vi-VN')}
                </p>
              </div>
            </div>
            {importResult.errors.length > 0 ? (
              <div className="flex-1 overflow-hidden flex flex-col">
                <p className="text-sm font-medium text-neutral-700 mb-2">
                  Các dòng cần sửa ({importResult.errors.length}
                  {importResult.truncated && '+'} dòng):
                </p>
                <div className="overflow-y-auto rounded-lg border border-neutral-200">
                  <table className="w-full text-sm">
                    <thead className="bg-neutral-50 sticky top-0">
                      <tr className="text-neutral-500 text-xs">
                        <th className="text-left px-3 py-2 font-medium">Dòng</th>
                        <th className="text-left px-3 py-2 font-medium">Lý do</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importResult.errors.map((e, idx) => (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2 text-neutral-700 font-medium">{e.row}</td>
                          <td className="px-3 py-2 text-neutral-600">{e.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
                ✓ Tất cả các dòng đã được xử lý thành công.
              </div>
            )}
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setImportResult(null)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sync safety stock result modal */}
      {syncResult && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Cập nhật ngưỡng AT</h3>
              <button
                onClick={() => setSyncResult(null)}
                className="p-1 rounded hover:bg-neutral-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3 mb-4">
              <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                <div className="text-xs text-blue-600 mb-1">Tháng dự báo</div>
                <div className="font-semibold text-blue-900">
                  {new Date(syncResult.forecast_month).toLocaleDateString('vi-VN', {
                    month: 'long',
                    year: 'numeric',
                  })}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-emerald-100 bg-emerald-50 p-3">
                  <p className="text-xs text-emerald-600 mb-1">Đã cập nhật</p>
                  <p className="text-2xl font-bold text-emerald-700 tabular-nums">
                    {syncResult.updated}
                  </p>
                </div>
                <div className="rounded-lg border border-amber-100 bg-amber-50 p-3">
                  <p className="text-xs text-amber-600 mb-1">Bỏ qua</p>
                  <p className="text-2xl font-bold text-amber-700 tabular-nums">
                    {syncResult.skipped}
                  </p>
                </div>
              </div>
              <div className="text-sm text-neutral-600 bg-neutral-50 border border-neutral-100 rounded-lg px-3 py-2">
                <strong>% Dự phòng:</strong> {syncResult.buffer_rate}%
              </div>
            </div>
            <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2 mb-4">
              ✓ {syncResult.message}
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setSyncResult(null)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function buildSupplyCode(category: string | undefined, id: number): string {
  // Map category → prefix mã vật tư theo design
  const prefix: Record<string, string> = {
    medicine: 'VT',
    mask: 'TB',
    glove: 'TB',
    test_kit: 'TB',
    disinfectant: 'HC',
    iv_fluid: 'VT',
    other: 'VT',
  };
  const p = prefix[category ?? ''] ?? 'VT';
  return `${p}-${String(id).padStart(4, '0')}`;
}

function ActionButton({
  variant,
  icon,
  children,
  onClick,
}: {
  variant: 'primary' | 'outline';
  icon?: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
}) {
  const base =
    'inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition';
  if (variant === 'primary') {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${base} bg-blue-600 text-white hover:bg-blue-700 shadow-sm`}
      >
        {icon}
        {children}
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${base} bg-white border border-neutral-200 text-neutral-700 hover:bg-neutral-50`}
    >
      {icon}
      {children}
    </button>
  );
}


// ── Add Supply Dialog (spec 6.2 #2) ──────────────────────────────────────────

function AddSupplyDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [vals, setVals] = useState({
    name: '',
    category: 'medicine',
    unit: 'Hộp',
    current_stock: 0,
    safety_stock: 0,
    expiry_date: '',
    lead_time_days: 0,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!vals.name.trim()) {
      setError('Tên vật tư không được để trống');
      return;
    }
    if (vals.current_stock < 0 || vals.safety_stock < 0) {
      setError('Tồn kho và ngưỡng AT phải >= 0');
      return;
    }
    try {
      setSubmitting(true);
      // Step 1: tạo MedicalSupply
      await api.post('/supplies/', {
        name: vals.name.trim(),
        category: vals.category,
        unit: vals.unit,
        lead_time_days: vals.lead_time_days || null,
      });
      // Step 2: tạo Inventory record qua batch-update / inventory direct
      // Ở đây dùng /inventory/import giả lập 1 dòng để có cả expiry_date
      const csv =
        'supply_code,supply_name,category,unit,current_stock,safety_stock,' +
        'expiry_date,supplier,lead_time_days\n' +
        `,${vals.name.trim()},${vals.category},${vals.unit},${vals.current_stock},` +
        `${vals.safety_stock},${vals.expiry_date},,${vals.lead_time_days}\n`;
      const blob = new Blob([csv], { type: 'text/csv' });
      const fd = new FormData();
      fd.append('file', blob, 'add_one.csv');
      await api.post('/inventory/import', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onSaved();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || err.message || 'Có lỗi xảy ra',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">Thêm vật tư mới</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-3">
          <Field label="Tên vật tư" required>
            <input
              type="text"
              required
              value={vals.name}
              onChange={(e) => setVals({ ...vals, name: e.target.value })}
              className={inputClass}
              placeholder="VD: Paracetamol 500mg"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Loại">
              <select
                value={vals.category}
                onChange={(e) => setVals({ ...vals, category: e.target.value })}
                className={inputClass}
              >
                {Object.entries(SUPPLY_CATEGORY_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Đơn vị tính">
              <input
                type="text"
                value={vals.unit}
                onChange={(e) => setVals({ ...vals, unit: e.target.value })}
                className={inputClass}
                placeholder="Hộp, Chai, Lọ, Cái..."
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Tồn kho hiện tại">
              <input
                type="number"
                min={0}
                value={vals.current_stock}
                onChange={(e) =>
                  setVals({ ...vals, current_stock: Math.max(0, Number(e.target.value)) })
                }
                className={inputClass}
              />
            </Field>
            <Field label="Ngưỡng an toàn">
              <input
                type="number"
                min={0}
                value={vals.safety_stock}
                onChange={(e) =>
                  setVals({ ...vals, safety_stock: Math.max(0, Number(e.target.value)) })
                }
                className={inputClass}
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Hạn dùng">
              <input
                type="date"
                value={vals.expiry_date}
                onChange={(e) => setVals({ ...vals, expiry_date: e.target.value })}
                className={inputClass}
              />
            </Field>
            <Field label="Lead time (ngày)">
              <input
                type="number"
                min={0}
                value={vals.lead_time_days}
                onChange={(e) =>
                  setVals({ ...vals, lead_time_days: Math.max(0, Number(e.target.value)) })
                }
                className={inputClass}
              />
            </Field>
          </div>
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50"
            >
              Huỷ
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-60"
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              Thêm vật tư
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const inputClass =
  'w-full h-10 px-3 rounded-lg border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500';

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-neutral-600 mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </span>
      {children}
    </label>
  );
}


// ── Edit Supply Dialog ──────────────────────────────────────────

function EditSupplyDialog({
  item,
  onClose,
  onSaved,
}: {
  item: InventoryRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [vals, setVals] = useState({
    current_stock: item.currentStock,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (vals.current_stock < 0) {
      setError('Tồn kho phải >= 0');
      return;
    }
    try {
      setSubmitting(true);
      await api.put(`/inventory/${item.id}`, vals);
      onSaved();
    } catch (err: any) {
      setError(
        err?.response?.data?.detail || err.message || 'Có lỗi xảy ra',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">Sửa vật tư</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-3">
          <div className="bg-neutral-50 rounded-lg p-3 mb-3">
            <div className="text-xs text-neutral-500 mb-1">Vật tư</div>
            <div className="font-semibold text-neutral-900">{item.name}</div>
            <div className="text-sm text-neutral-600 mt-0.5">
              Mã: {item.code} · Loại: {item.category}
            </div>
          </div>
          <Field label="Tồn kho hiện tại">
            <input
              type="number"
              min={0}
              value={vals.current_stock}
              onChange={(e) =>
                setVals({ ...vals, current_stock: Math.max(0, Number(e.target.value)) })
              }
              className={inputClass}
            />
          </Field>
          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50"
            >
              Huỷ
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-60"
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              Cập nhật
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


// ── Confirm Delete Dialog ──────────────────────────────────────────

function ConfirmDeleteDialog({
  item,
  onClose,
  onConfirm,
}: {
  item: InventoryRow;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [submitting, setSubmitting] = useState(false);

  const handleConfirm = async () => {
    setSubmitting(true);
    await onConfirm();
    setSubmitting(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">Xác nhận xoá</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-5 py-4">
          <p className="text-sm text-neutral-600 mb-3">
            Bạn có chắc chắn muốn xoá vật tư này không?
          </p>
          <div className="bg-red-50 rounded-lg p-3 mb-4">
            <div className="font-semibold text-neutral-900">{item.name}</div>
            <div className="text-sm text-neutral-600 mt-0.5">
              Mã: {item.code} • Tồn kho: {item.currentStock} {item.unit}
            </div>
          </div>
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-60"
            >
              Huỷ
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={submitting}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-60"
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              Xoá
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
