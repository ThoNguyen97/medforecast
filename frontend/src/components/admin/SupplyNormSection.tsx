import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, Loader2, Search } from 'lucide-react';

import {
  adminSeverityService,
  type NormUpsert,
  type NormMatrix,
} from '../../services/adminSeverityService';

const DISEASES = [
  { code: 'J20', name: 'Viêm phế quản cấp' },
  { code: 'J06', name: 'Nhiễm trùng đường hô hấp trên cấp' },
  { code: 'J02', name: 'Viêm họng cấp' },
  { code: 'J01', name: 'Viêm xoang cấp' },
];

/**
 * Admin section: Quản lý định mức thuốc/vật tư theo bệnh × mức độ.
 *
 * UI: chọn bệnh → hiển thị ma trận 15 thuốc × 3 mức độ. Sửa inline + Lưu tất cả.
 */
export default function SupplyNormSection() {
  const queryClient = useQueryClient();
  const [selectedDisease, setSelectedDisease] = useState<string>('J20');
  const [draft, setDraft] = useState<Record<number, { mild: number; moderate: number; severe: number }>>(
    {},
  );
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Phân trang
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Tìm kiếm
  const [search, setSearch] = useState('');

  const { data, isLoading, refetch } = useQuery<NormMatrix>({
    queryKey: ['admin', 'supply-norms', selectedDisease],
    queryFn: () => adminSeverityService.getNormMatrix(selectedDisease),
  });

  // Khi load matrix mới → init draft
  useEffect(() => {
    if (data?.supplies) {
      const initial: Record<number, { mild: number; moderate: number; severe: number }> = {};
      data.supplies.forEach((s) => {
        initial[s.supply_id] = {
          mild: s.mild,
          moderate: s.moderate,
          severe: s.severe,
        };
      });
      setDraft(initial);
      setSuccess(null);
      setError(null);
      setCurrentPage(1); // Reset về trang 1 khi đổi bệnh
    }
  }, [data]);

  const bulkMutation = useMutation({
    mutationFn: (norms: NormUpsert[]) =>
      adminSeverityService.bulkUpsertNorms(norms),
    onSuccess: (result) => {
      setSuccess(
        `Đã lưu thành công: ${result.created} mới + ${result.updated} cập nhật.`,
      );
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['admin', 'supply-norms'] });
      queryClient.invalidateQueries({ queryKey: ['supply-recommendations'] });
      refetch();
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? err?.message ?? 'Lỗi';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      setSuccess(null);
    },
  });

  // Phát hiện thay đổi
  const hasChanges = useMemo(() => {
    if (!data?.supplies) return false;
    return data.supplies.some((s) => {
      const d = draft[s.supply_id];
      if (!d) return false;
      return d.mild !== s.mild || d.moderate !== s.moderate || d.severe !== s.severe;
    });
  }, [data, draft]);

  const updateCell = (
    supplyId: number,
    severity: 'mild' | 'moderate' | 'severe',
    value: number,
  ) => {
    setDraft((prev) => ({
      ...prev,
      [supplyId]: {
        ...(prev[supplyId] ?? { mild: 0, moderate: 0, severe: 0 }),
        [severity]: value,
      },
    }));
  };

  const saveAll = () => {
    if (!data?.supplies) return;
    const norms: NormUpsert[] = [];
    for (const s of data.supplies) {
      const d = draft[s.supply_id];
      if (!d) continue;
      // Chỉ gửi những thuốc có thay đổi
      if (d.mild !== s.mild) {
        norms.push({
          icd_code: selectedDisease,
          severity: 'mild',
          supply_id: s.supply_id,
          quantity_per_case: d.mild,
        });
      }
      if (d.moderate !== s.moderate) {
        norms.push({
          icd_code: selectedDisease,
          severity: 'moderate',
          supply_id: s.supply_id,
          quantity_per_case: d.moderate,
        });
      }
      if (d.severe !== s.severe) {
        norms.push({
          icd_code: selectedDisease,
          severity: 'severe',
          supply_id: s.supply_id,
          quantity_per_case: d.severe,
        });
      }
    }
    if (norms.length === 0) return;
    bulkMutation.mutate(norms);
  };

  // Phân trang
  const supplies = data?.supplies || [];
  const filteredSupplies = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return supplies;
    return supplies.filter((s) => {
      const haystack = `${s.supply_code} ${s.drug_code ?? ''} ${s.ten_hoat_chat} ${s.group_name ?? ''}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [supplies, search]);

  const totalPages = Math.ceil(filteredSupplies.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedSupplies = filteredSupplies.slice(startIndex, endIndex);

  // Reset page khi đổi từ khoá tìm kiếm
  useEffect(() => {
    setCurrentPage(1);
  }, [search]);

  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-100 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h3 className="text-base font-semibold text-neutral-900">
            Định mức thuốc/vật tư theo bệnh và mức độ
          </h3>
          <p className="text-xs text-neutral-500 mt-1 max-w-xl">
            Số lượng thuốc/vật tư cần dùng cho 1 ca bệnh ở từng mức độ. Hệ thống dùng
            các giá trị này × số ca dự báo để tính nhu cầu kho.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedDisease}
            onChange={(e) => setSelectedDisease(e.target.value)}
            className="px-3 py-2 border border-neutral-200 rounded-lg text-sm"
          >
            {DISEASES.map((d) => (
              <option key={d.code} value={d.code}>
                {d.code} - {d.name}
              </option>
            ))}
          </select>
          <button
            onClick={saveAll}
            disabled={!hasChanges || bulkMutation.isPending}
            className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
          >
            {bulkMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Lưu thay đổi
          </button>
        </div>
      </div>

      {success && (
        <div className="mx-5 mt-3 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-700">
          {success}
        </div>
      )}
      {error && (
        <div className="mx-5 mt-3 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
          {error}
        </div>
      )}

      {/* Thanh tìm kiếm thuốc */}
      <div className="px-5 py-3 border-b border-neutral-100 bg-neutral-50/50">
        <div className="relative max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo mã, tên hoạt chất, nhóm..."
            className="w-full h-10 pl-9 pr-3 rounded-lg border border-neutral-200 bg-white text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 border-b border-neutral-100">
            <tr className="text-left text-xs uppercase tracking-wide text-neutral-500">
              <th className="px-4 py-3 font-semibold">Mã VT</th>
              <th className="px-4 py-3 font-semibold">Tên hoạt chất</th>
              <th className="px-4 py-3 font-semibold">Nhóm</th>
              <th className="px-4 py-3 font-semibold text-center">ĐVT</th>
              <th className="px-4 py-3 font-semibold text-center bg-emerald-50/60">
                Nhẹ
              </th>
              <th className="px-4 py-3 font-semibold text-center bg-amber-50/60">
                Trung bình
              </th>
              <th className="px-4 py-3 font-semibold text-center bg-red-50/60">
                Nặng
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={7} className="text-center py-8 text-neutral-500">
                  Đang tải...
                </td>
              </tr>
            )}
            {!isLoading && paginatedSupplies.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-8 text-neutral-500">
                  {search.trim()
                    ? 'Không tìm thấy thuốc/vật tư phù hợp.'
                    : 'Không có dữ liệu.'}
                </td>
              </tr>
            )}
            {paginatedSupplies.map((s) => {
              const d = draft[s.supply_id] ?? {
                mild: s.mild,
                moderate: s.moderate,
                severe: s.severe,
              };
              const isModified =
                d.mild !== s.mild ||
                d.moderate !== s.moderate ||
                d.severe !== s.severe;
              return (
                <tr
                  key={s.supply_id}
                  className={`border-b border-neutral-50 ${
                    isModified ? 'bg-yellow-50/40' : 'hover:bg-neutral-50/60'
                  }`}
                >
                  <td className="px-4 py-3 font-mono text-xs text-neutral-700">
                    {s.supply_code}
                  </td>
                  <td className="px-4 py-3 font-medium text-neutral-900">
                    {s.ten_hoat_chat}
                    <div className="text-[11px] text-neutral-500 font-normal">
                      {s.drug_code}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-600">
                    {s.group_name}
                  </td>
                  <td className="px-4 py-3 text-center text-xs text-neutral-500">
                    {s.unit}
                  </td>
                  <td className="px-4 py-3 text-center bg-emerald-50/30">
                    <input
                      type="number"
                      min="0"
                      value={d.mild}
                      onChange={(e) =>
                        updateCell(s.supply_id, 'mild', Number(e.target.value))
                      }
                      className="w-16 px-2 py-1 border border-neutral-300 rounded text-sm text-center"
                    />
                  </td>
                  <td className="px-4 py-3 text-center bg-amber-50/30">
                    <input
                      type="number"
                      min="0"
                      value={d.moderate}
                      onChange={(e) =>
                        updateCell(
                          s.supply_id,
                          'moderate',
                          Number(e.target.value),
                        )
                      }
                      className="w-16 px-2 py-1 border border-neutral-300 rounded text-sm text-center"
                    />
                  </td>
                  <td className="px-4 py-3 text-center bg-red-50/30">
                    <input
                      type="number"
                      min="0"
                      value={d.severe}
                      onChange={(e) =>
                        updateCell(
                          s.supply_id,
                          'severe',
                          Number(e.target.value),
                        )
                      }
                      className="w-16 px-2 py-1 border border-neutral-300 rounded text-sm text-center"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer phân trang */}
      {filteredSupplies.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-t border-neutral-100 text-sm text-neutral-500">
          <span className="text-xs">
            Hiển thị {startIndex + 1}-{Math.min(endIndex, filteredSupplies.length)} trong số {filteredSupplies.length} thuốc/vật tư
            {search.trim() && supplies.length !== filteredSupplies.length && (
              <span className="text-neutral-400"> (đã lọc từ {supplies.length})</span>
            )}
          </span>
          
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1.5 text-xs border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Trước
              </button>
              
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      className={`w-8 h-8 text-xs rounded-lg ${
                        currentPage === pageNum
                          ? 'bg-blue-600 text-white font-medium'
                          : 'border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
              </div>
              
              <button
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
                className="px-3 py-1.5 text-xs border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Sau
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
