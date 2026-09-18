import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Upload, FileDown, Plus, Loader2, X } from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { useAuthStore } from '../store/authStore';
import { useInventory } from '../hooks/useInventory';
import api from '../services/api';
import { dssService } from '../services/dssService';
import { SUPPLY_CATEGORY_LABELS } from '../utils/constants';
import type { AlertLevel, AlertRow } from '../types/dashboardV2';
import InventoryAlertCard from '../components/inventory/InventoryAlertCard';
import InventoryToolbar, {
  type InventoryFilters,
} from '../components/inventory/InventoryToolbar';
import InventoryTable, {
  type InventoryRow,
} from '../components/inventory/InventoryTable';

const PAGE_SIZE = 10;

/**
 * Module 6 — Quản lý thuốc (13/09/2026, trước đó là "Vật tư y tế & Kho vận").
 *
 * Danh mục app chỉ có THUỐC (`TM_DUOC` loại 'T', phương án A) nên trang đổi
 * tên cho đúng nội dung. Nhãn trên mỗi dòng là nhãn DOI từ
 * `/dashboard/v2/alerts?focus=false` — CÙNG chuỗi Tầng 1→2→3 với Tổng quan và
 * Cảnh báo; hệ nhãn "Ngưỡng an toàn / Nguy cấp" theo `safety_stock` (cột chỉ
 * có giá trị ở 34/5.051 dòng) đã bỏ hẳn.
 *
 * Nguồn dữ liệu: `/inventory` cho danh mục + id để sửa/xoá; `/dashboard/v2/alerts`
 * cho DOI. Ghép theo `supply_code` ở client. Mã không có tiêu hao trong 12 kỳ
 * đã chốt (không có mẫu số) ẩn mặc định — bật lại bằng ô "Hiện cả mã không
 * tiêu hao".
 */
export default function Inventory() {
  const { setPageTitle } = useUIStore();

  useEffect(() => {
    setPageTitle('Quản lý thuốc');
  }, [setPageTitle]);

  return <InventoryContent />;
}

function InventoryContent() {
  // Import / thêm mới đi qua POST /inventory/import — endpoint đòi
  // get_inventory_manager_or_admin; không có quyền mà vẫn hiện nút thì bấm
  // vào chỉ nhận 403.
  // PHẢI khai ở ĐÂY chứ không phải ở Inventory(): các nút dùng biến này nằm
  // trong InventoryContent — khai nhầm chỗ thì lúc chạy ném ReferenceError và
  // React gỡ toàn bộ cây (trắng cả trang).
  const { user } = useAuthStore();
  const duocSuaKho =
    user?.role === 'Administrator' || user?.role === 'Inventory_Manager';

  const [filters, setFilters] = useState<InventoryFilters>({
    search: '',
    category: 'all',
    status: 'all',
    showUnmeasured: false,
  });
  const [page, setPage] = useState(1);
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

  const { data: inventory = [], isLoading, refetch } = useInventory({ limit: 5000 });

  // Toàn danh mục DOI, một lần (limit 2000 > 1.476 mã có tiêu hao 12 kỳ).
  const doiQuery = useQuery({
    queryKey: ['dss', 'alerts', 'inventory-page'],
    queryFn: () => dssService.getAlerts({ focus: false, level: null, limit: 2000, offset: 0 }),
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const doiRows = doiQuery.data?.rows;
  const doiByCode = useMemo(() => {
    const m = new Map<string, AlertRow>();
    (doiRows ?? []).forEach((r) => m.set(r.supply_code, r));
    return m;
  }, [doiRows]);

  // Danh mục (/inventory) ghép DOI (/dashboard/v2/alerts) theo supply_code.
  const allRows: InventoryRow[] = useMemo(() => {
    return inventory.map((item: any, idx: number) => {
      const supply = item.supply ?? {};
      const code: string = supply.supply_code ?? `#${item.supply_id ?? item.id ?? idx}`;
      const d = doiByCode.get(code);
      return {
        id: item.id,
        code,
        name: supply.ten_hoat_chat ?? d?.ten ?? '—',
        category: d?.danh_muc ?? nhanDanhMuc(supply.category),
        group: supply.group_name ?? d?.nhom ?? '',
        unit: supply.unit ?? d?.don_vi ?? '—',
        currentStock: d ? d.s_total : item.current_stock ?? 0,
        usableStock: d ? d.s_usable : null,
        dDaily: d ? d.d_daily : null,
        doi: d?.doi ?? null,
        level: d?.muc ?? null,
        greyReason: d?.ly_do_xam ?? null,
      };
    });
  }, [inventory, doiByCode]);

  const categoryOptions = useMemo(() => {
    const unique = new Set<string>();
    allRows.forEach((r) => {
      if (r.category && r.category !== '—') unique.add(r.category);
    });
    return Array.from(unique)
      .sort((a, b) => a.localeCompare(b, 'vi'))
      .map((key) => ({ key, label: key }));
  }, [allRows]);

  const filtered = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return allRows.filter((r) => {
      if (!filters.showUnmeasured && r.level === null) return false;
      if (q && !`${r.code} ${r.name}`.toLowerCase().includes(q)) return false;
      if (filters.category !== 'all' && r.category !== filters.category) return false;
      if (filters.status === 'unmeasured') return r.level === null;
      if (filters.status !== 'all' && r.level !== filters.status) return false;
      return true;
    });
  }, [allRows, filters]);

  const counts = useMemo(() => {
    const c: Record<AlertLevel, number> = { red: 0, amber: 0, green: 0, grey: 0 };
    allRows.forEach((r) => {
      if (r.level) c[r.level] += 1;
    });
    return c;
  }, [allRows]);

  const paged = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page]);

  useEffect(() => {
    setPage(1);
  }, [filters.search, filters.category, filters.status, filters.showUnmeasured]);

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
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `danh_muc_thuoc_${new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)}.xlsx`;
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
      doiQuery.refetch();
    } catch (err: any) {
      alert('Lỗi import: ' + (err?.response?.data?.detail || err.message || 'không xác định'));
    } finally {
      setImporting(false);
    }
  };

  const confirmDelete = async () => {
    if (!deletingItem) return;
    try {
      await api.delete(`/inventory/${deletingItem.id}`);
      refetch();
      setDeletingItem(null);
    } catch (err: any) {
      alert('Lỗi xoá thuốc: ' + (err?.response?.data?.detail || err.message || 'không xác định'));
    }
  };

  const th = doiQuery.data?.meta.thresholds;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">Quản lý thuốc</h2>
          <p className="text-sm text-neutral-500 mt-1">
            Danh mục thuốc của bệnh viện, tồn kho theo lô và nhãn DOI — cùng cách tính với
            trang Cảnh báo thiếu hụt.
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
            icon={exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            onClick={handleExportExcel}
          >
            {exporting ? 'Đang xuất...' : 'Xuất Excel'}
          </ActionButton>
          <ActionButton variant="outline" icon={<FileDown className="w-4 h-4" />} onClick={handleDownloadTemplate}>
            Tải template mẫu
          </ActionButton>
          {duocSuaKho && (
            <ActionButton
              variant="outline"
              icon={importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              onClick={() => fileInputRef.current?.click()}
            >
              {importing ? 'Đang import...' : 'Import tồn kho đầu kỳ'}
            </ActionButton>
          )}
          {duocSuaKho && (
            <ActionButton variant="primary" icon={<Plus className="w-4 h-4" />} onClick={() => setShowAddForm(true)}>
              Thêm thuốc
            </ActionButton>
          )}
        </div>
      </div>

      <InventoryAlertCard
        counts={counts}
        redDays={th?.red_days ?? null}
        amberDays={th?.amber_days ?? null}
      />

      {doiQuery.isError && (
        <div className="text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
          Không tải được nhãn DOI (/dashboard/v2/alerts) — bảng dưới chỉ hiện danh mục và tồn kho.
        </div>
      )}

      <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
        <InventoryToolbar filters={filters} onChange={setFilters} categories={categoryOptions} />
        <InventoryTable
          rows={paged}
          isLoading={isLoading || (doiQuery.isLoading && !doiQuery.isError)}
          total={filtered.length}
          page={page}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
          onEdit={duocSuaKho ? setEditingItem : undefined}
          onDelete={duocSuaKho ? setDeletingItem : undefined}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-400 pt-2 border-t border-neutral-100">
        <span>© 2026 MedForecast AI. Vận hành bởi Phòng Công nghệ Thông tin Y tế.</span>
        <div className="flex items-center gap-4">
          <a className="hover:text-neutral-600" href="#">Điều khoản</a>
          <a className="hover:text-neutral-600" href="#">Bảo mật</a>
          <a className="hover:text-neutral-600" href="#">Hướng dẫn sử dụng</a>
        </div>
      </div>

      {showAddForm && (
        <AddSupplyDialog
          onClose={() => setShowAddForm(false)}
          onSaved={() => {
            setShowAddForm(false);
            refetch();
          }}
        />
      )}

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

      {deletingItem && (
        <ConfirmDeleteDialog item={deletingItem} onClose={() => setDeletingItem(null)} onConfirm={confirmDelete} />
      )}

      {importResult && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-2xl shadow-xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Kết quả import tồn kho</h3>
              <button onClick={() => setImportResult(null)} className="p-1 rounded hover:bg-neutral-100">
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
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** `category` từ HIS đã là nhãn tiếng Việt; chỉ dữ liệu import tay đời trước
 * mới còn khoá kiểu `medicine`. */
function nhanDanhMuc(category: string | null | undefined): string {
  if (!category) return 'Khác';
  return SUPPLY_CATEGORY_LABELS[category] ?? category;
}

/** 8 nhãn danh mục thuốc cho hộp thoại Thêm (không gồm khoá VTYT/legacy). */
const DANH_MUC_THUOC = Object.keys(SUPPLY_CATEGORY_LABELS).filter(
  (k) => SUPPLY_CATEGORY_LABELS[k] === k,
);

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
    category: 'Khác',
    unit: 'Viên',
    current_stock: 0,
    expiry_date: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!vals.name.trim()) {
      setError('Tên thuốc không được để trống');
      return;
    }
    if (vals.current_stock < 0) {
      setError('Tồn kho phải >= 0');
      return;
    }
    try {
      setSubmitting(true);
      // MỘT lệnh duy nhất: POST /inventory/import tự tạo MedicalSupply nếu chưa
      // có (sinh supply_code dạng VT_AUTO_... khi để trống) rồi tạo luôn dòng
      // tồn kho kèm hạn dùng.
      // KHÔNG gọi POST /supplies/ nữa: schema MedicalSupplyCreate bắt buộc
      // supply_code, drug_code, ten_hoat_chat, group_name và không có trường
      // 'name', nên lệnh cũ luôn 422; endpoint đó còn đòi quyền Administrator
      // trong khi màn hình này mở cho cả Inventory_Manager.
      const oCsv = (v: string | number) => {
        const t = String(v ?? '');
        return /[",\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
      };
      const csv =
        'supply_code,drug_code,ten_hoat_chat,unit,group_name,category,' +
        'current_stock,safety_stock,expiry_date\n' +
        [
          '',
          '',
          oCsv(vals.name.trim()),
          oCsv(vals.unit),
          oCsv(vals.category),
          oCsv(vals.category),
          vals.current_stock,
          0,
          vals.expiry_date,
        ].join(',') + '\n';
      const blob = new Blob([csv], { type: 'text/csv' });
      const fd = new FormData();
      fd.append('file', blob, 'add_one.csv');
      const res = await api.post('/inventory/import', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      // Endpoint trả 200 kèm danh sách dòng bị bỏ qua chứ không ném lỗi — nếu
      // không kiểm thì hộp thoại đóng lại như thể đã thêm xong.
      const kq = res?.data ?? {};
      if (((kq.imported ?? 0) + (kq.updated ?? 0)) === 0) {
        setError(
          kq.errors?.[0]?.reason
            ? `Không thêm được: ${kq.errors[0].reason}`
            : 'Không thêm được thuốc — máy chủ không nhận dòng nào.',
        );
        return;
      }
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
          <h3 className="text-base font-semibold text-neutral-900">Thêm thuốc mới</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-3">
          <Field label="Tên thuốc" required>
            <input
              type="text"
              required
              value={vals.name}
              onChange={(e) => setVals({ ...vals, name: e.target.value })}
              className={inputClass}
              placeholder="VD: Paracetamol"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Danh mục">
              <select
                value={vals.category}
                onChange={(e) => setVals({ ...vals, category: e.target.value })}
                className={inputClass}
              >
                {DANH_MUC_THUOC.map((k) => (
                  <option key={k} value={k}>
                    {k}
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
                placeholder="Viên, Chai, Lọ, Ống..."
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
            <Field label="Hạn dùng">
              <input
                type="date"
                value={vals.expiry_date}
                onChange={(e) => setVals({ ...vals, expiry_date: e.target.value })}
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
              Thêm thuốc
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
          <h3 className="text-base font-semibold text-neutral-900">Sửa thuốc</h3>
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
            <div className="text-xs text-neutral-500 mb-1">Thuốc</div>
            <div className="font-semibold text-neutral-900">{item.name}</div>
            <div className="text-sm text-neutral-600 mt-0.5">
              Mã: {item.code} · Danh mục: {item.category}
            </div>
          </div>
          <Field label="Tồn kho đầu kỳ (chỉ dùng khi chưa có ảnh chụp lô từ HIS)">
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
            Bạn có chắc chắn muốn xoá thuốc này không?
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
