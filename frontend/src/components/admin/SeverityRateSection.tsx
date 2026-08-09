import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Pencil, Save, X, Sparkles, Eye, Loader2 } from 'lucide-react';

import {
  adminSeverityService,
  type SeverityRate,
} from '../../services/adminSeverityService';
import api from '../../services/api';

/**
 * Admin section: Quản lý tỷ lệ Nhẹ/TB/Nặng cho 4 bệnh.
 */
export default function SeverityRateSection() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['admin', 'severity-rates'],
    queryFn: () => adminSeverityService.listSeverityRates(),
  });

  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<{
    mild_rate: number;
    moderate_rate: number;
    severe_rate: number;
    note: string;
  }>({ mild_rate: 0, moderate_rate: 0, severe_rate: 0, note: '' });
  const [error, setError] = useState<string | null>(null);

  const updateMutation = useMutation({
    mutationFn: (p: {
      icd_code: string;
      payload: {
        mild_rate: number;
        moderate_rate: number;
        severe_rate: number;
        note?: string;
      };
    }) => adminSeverityService.updateSeverityRate(p.icd_code, p.payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'severity-rates'] });
      // invalidate cả supply-recommendations để tính lại
      queryClient.invalidateQueries({ queryKey: ['supply-recommendations'] });
      setEditingId(null);
      setError(null);
    },
    onError: (err: any) => {
      const detail =
        err?.response?.data?.detail ?? err?.message ?? 'Có lỗi xảy ra';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    },
  });

  // Auto suy luận từ dữ liệu lịch sử (mục 5.2)
  const [recomputeResult, setRecomputeResult] = useState<any>(null);
  const recomputeMutation = useMutation({
    mutationFn: (force: boolean) =>
      api
        .post(`/admin/severity-rates/recompute?force=${force}`)
        .then((r) => r.data),
    onSuccess: (data) => {
      setRecomputeResult(data);
      queryClient.invalidateQueries({ queryKey: ['admin', 'severity-rates'] });
      queryClient.invalidateQueries({ queryKey: ['supply-recommendations'] });
      setError(null);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? err?.message ?? 'Lỗi';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    },
  });

  const startEdit = (rate: SeverityRate) => {
    setEditingId(rate.id);
    setDraft({
      mild_rate: rate.mild_rate,
      moderate_rate: rate.moderate_rate,
      severe_rate: rate.severe_rate,
      note: rate.note ?? '',
    });
    setError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setError(null);
  };

  const saveEdit = (rate: SeverityRate) => {
    const total = draft.mild_rate + draft.moderate_rate + draft.severe_rate;
    if (Math.abs(total - 100) > 0.01) {
      setError(`Tổng tỷ lệ phải = 100% (hiện: ${total}%)`);
      return;
    }
    updateMutation.mutate({
      icd_code: rate.icd_code,
      payload: {
        mild_rate: draft.mild_rate,
        moderate_rate: draft.moderate_rate,
        severe_rate: draft.severe_rate,
        note: draft.note || undefined,
      },
    });
  };

  return (
    <div className="space-y-4">
      {/* Auto-recompute card (mục 5.2) */}
      <div className="bg-gradient-to-br from-violet-50 to-blue-50 border border-violet-200 rounded-xl p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1.5">
              <Sparkles className="w-4 h-4 text-violet-600" />
              <h3 className="text-sm font-semibold text-violet-900">
                Suy luận tỷ lệ tự động từ dữ liệu lịch sử
              </h3>
            </div>
            <p className="text-xs text-neutral-600 leading-relaxed max-w-2xl">
              Hệ thống phân loại từng ca bệnh thành Nhẹ / Trung bình / Nặng dựa trên
              LengthOfStay, SubICD_Count và loại thuốc/vật tư đã sử dụng, sau đó tính
              lại tỷ lệ % cho 4 bệnh.
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => recomputeMutation.mutate(false)}
              disabled={recomputeMutation.isPending}
              className="px-3 py-2 bg-white border border-violet-300 text-violet-700 text-xs font-medium rounded-lg hover:bg-violet-50 disabled:opacity-50 flex items-center gap-1.5"
            >
              {recomputeMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Eye className="w-3.5 h-3.5" />
              )}
              Cập nhật (giữ severity cũ)
            </button>
            <button
              onClick={() => {
                if (
                  window.confirm(
                    'Xóa toàn bộ severity hiện có và phân loại lại từ đầu?',
                  )
                ) {
                  recomputeMutation.mutate(true);
                }
              }}
              disabled={recomputeMutation.isPending}
              className="px-3 py-2 bg-violet-600 text-white text-xs font-medium rounded-lg hover:bg-violet-700 disabled:opacity-50 flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Phân loại lại toàn bộ
            </button>
          </div>
        </div>

        {recomputeResult && (
          <div className="mt-4 bg-white rounded-lg p-3 border border-violet-100">
            <div className="text-xs font-semibold text-violet-900 mb-2">
              Kết quả: {recomputeResult.summary.updated} bệnh đã cập nhật,{' '}
              {recomputeResult.summary.skipped} bỏ qua.
            </div>
            <div className="space-y-1">
              {recomputeResult.diseases.map((d: any) => (
                <div
                  key={d.icd_code}
                  className="text-xs flex items-center gap-2 text-neutral-700"
                >
                  <span className="font-mono w-12">{d.icd_code}</span>
                  <span className="flex-1">{d.disease_name}</span>
                  {d.status === 'updated' ? (
                    <span className="text-emerald-700">
                      {d.total_cases} ca · {d.new.mild_rate}/
                      {d.new.moderate_rate}/{d.new.severe_rate}%
                    </span>
                  ) : (
                    <span className="text-neutral-400 italic">
                      {d.reason}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Severity rate table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">
            Tỷ lệ phân bổ ca bệnh (Nhẹ / Trung bình / Nặng)
          </h3>
          <p className="text-xs text-neutral-500 mt-1">
            Tỷ lệ % dùng để phân bổ tổng số ca dự báo theo 3 mức độ. Tổng phải bằng 100%.
          </p>
        </div>

      {error && (
        <div className="mx-5 mt-3 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50 border-b border-neutral-100">
            <tr className="text-left text-xs uppercase tracking-wide text-neutral-500">
              <th className="px-4 py-3 font-semibold">ICD</th>
              <th className="px-4 py-3 font-semibold">Bệnh</th>
              <th className="px-4 py-3 font-semibold text-center">Nhẹ (%)</th>
              <th className="px-4 py-3 font-semibold text-center">Trung bình (%)</th>
              <th className="px-4 py-3 font-semibold text-center">Nặng (%)</th>
              <th className="px-4 py-3 font-semibold">Ghi chú</th>
              <th className="px-4 py-3 font-semibold w-24" />
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
            {data?.map((rate) => {
              const isEditing = editingId === rate.id;
              return (
                <tr
                  key={rate.id}
                  className="border-b border-neutral-50 hover:bg-neutral-50/60"
                >
                  <td className="px-4 py-3 font-mono text-xs text-neutral-700">
                    {rate.icd_code}
                  </td>
                  <td className="px-4 py-3 font-medium text-neutral-900">
                    {rate.disease_name}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {isEditing ? (
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={draft.mild_rate}
                        onChange={(e) =>
                          setDraft({ ...draft, mild_rate: Number(e.target.value) })
                        }
                        className="w-20 px-2 py-1 border border-neutral-300 rounded text-sm text-center"
                      />
                    ) : (
                      <span className="text-emerald-700 font-semibold">
                        {rate.mild_rate}%
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {isEditing ? (
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={draft.moderate_rate}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            moderate_rate: Number(e.target.value),
                          })
                        }
                        className="w-20 px-2 py-1 border border-neutral-300 rounded text-sm text-center"
                      />
                    ) : (
                      <span className="text-amber-700 font-semibold">
                        {rate.moderate_rate}%
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {isEditing ? (
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="100"
                        value={draft.severe_rate}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            severe_rate: Number(e.target.value),
                          })
                        }
                        className="w-20 px-2 py-1 border border-neutral-300 rounded text-sm text-center"
                      />
                    ) : (
                      <span className="text-red-700 font-semibold">
                        {rate.severe_rate}%
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-600 max-w-md">
                    {isEditing ? (
                      <input
                        type="text"
                        value={draft.note}
                        onChange={(e) =>
                          setDraft({ ...draft, note: e.target.value })
                        }
                        className="w-full px-2 py-1 border border-neutral-300 rounded text-xs"
                        placeholder="Ghi chú"
                      />
                    ) : (
                      rate.note ?? '—'
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {isEditing ? (
                      <div className="flex gap-1">
                        <button
                          onClick={() => saveEdit(rate)}
                          disabled={updateMutation.isPending}
                          className="p-1.5 rounded hover:bg-emerald-100 text-emerald-700"
                          title="Lưu"
                        >
                          <Save className="w-4 h-4" />
                        </button>
                        <button
                          onClick={cancelEdit}
                          className="p-1.5 rounded hover:bg-neutral-100 text-neutral-700"
                          title="Hủy"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => startEdit(rate)}
                        className="p-1.5 rounded hover:bg-blue-100 text-blue-700"
                        title="Sửa"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      </div>
    </div>
  );
}
