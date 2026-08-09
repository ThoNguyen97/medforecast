import { useState } from 'react';
import { Filter, Loader2, Pencil, X } from 'lucide-react';
import {
  forecastAnalysisService,
  type ForecastHistoryItem,
} from '../../services/forecastAnalysisService';

interface Props {
  rows: ForecastHistoryItem[];
  isLoading?: boolean;
  onUpdated?: () => void;
}

export default function ForecastHistoryTable({
  rows,
  isLoading,
  onUpdated,
}: Props) {
  const [editingActual, setEditingActual] = useState<ForecastHistoryItem | null>(null);
  const [showFilter, setShowFilter] = useState(false);
  const [filterMonth, setFilterMonth] = useState<string>('all'); // 'all' hoặc 'MM/YYYY'
  const [filterDisease, setFilterDisease] = useState<string>('all');

  // Lấy danh sách unique tháng và bệnh từ rows
  const uniqueMonths = Array.from(new Set(rows.map((r) => r.month))).sort();
  const uniqueDiseases = Array.from(
    new Set(rows.map((r) => r.disease_label))
  ).sort();

  // Lọc rows theo filter
  const filteredRows = rows.filter((r) => {
    if (filterMonth !== 'all' && r.month !== filterMonth) return false;
    if (filterDisease !== 'all' && r.disease_label !== filterDisease) return false;
    return true;
  });

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4">
        <h3 className="text-sm font-semibold text-neutral-900">
          Lịch sử dự báo gần đây
        </h3>
        <button
          type="button"
          onClick={() => setShowFilter(!showFilter)}
          className={`w-9 h-9 inline-flex items-center justify-center rounded-lg text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50 ${
            showFilter ? 'bg-blue-50 text-blue-600' : ''
          }`}
          aria-label="Lọc lịch sử"
        >
          <Filter className="w-4 h-4" />
        </button>
      </div>

      {/* Filter panel */}
      {showFilter && (
        <div className="px-5 py-3 bg-neutral-50 border-y border-neutral-100 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs font-medium text-neutral-600 mb-1.5 block">
                Tháng
              </span>
              <select
                value={filterMonth}
                onChange={(e) => setFilterMonth(e.target.value)}
                className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              >
                <option value="all">Tất cả các tháng</option>
                {uniqueMonths.map((m) => (
                  <option key={m} value={m}>
                    Tháng {m}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-neutral-600 mb-1.5 block">
                Bệnh
              </span>
              <select
                value={filterDisease}
                onChange={(e) => setFilterDisease(e.target.value)}
                className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              >
                <option value="all">Tất cả bệnh</option>
                {uniqueDiseases.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {(filterMonth !== 'all' || filterDisease !== 'all') && (
            <button
              type="button"
              onClick={() => {
                setFilterMonth('all');
                setFilterDisease('all');
              }}
              className="text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              Xóa bộ lọc
            </button>
          )}
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-neutral-500 text-xs border-y border-neutral-100">
            <th className="text-left px-5 py-3 font-medium">Tháng</th>
            <th className="text-left px-5 py-3 font-medium">Số ca dự báo</th>
            <th className="text-left px-5 py-3 font-medium">Số ca thực tế</th>
            <th className="text-left px-5 py-3 font-medium">Độ lệch</th>
            <th className="text-right px-5 py-3 font-medium w-32">Thao tác</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            <tr>
              <td colSpan={5} className="py-8">
                <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Đang tải lịch sử...
                </div>
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-10 text-center text-sm text-neutral-400">
                Chưa có lịch sử dự báo
              </td>
            </tr>
          ) : filteredRows.length === 0 ? (
            <tr>
              <td colSpan={5} className="py-10 text-center text-sm text-neutral-400">
                Không tìm thấy kết quả phù hợp với bộ lọc
              </td>
            </tr>
          ) : (
            filteredRows.map((r) => (
              <tr key={r.id} className="border-t border-neutral-100">
                <td className="px-5 py-3.5 text-neutral-700">Tháng {r.month}</td>
                <td className="px-5 py-3.5 text-neutral-700 tabular-nums">
                  {r.predicted_cases.toLocaleString('vi-VN')}
                </td>
                <td className="px-5 py-3.5 text-neutral-700 tabular-nums">
                  {r.actual_cases !== null
                    ? r.actual_cases.toLocaleString('vi-VN')
                    : '—'}
                </td>
                <td className="px-5 py-3.5">
                  <DeviationPill value={r.deviation_pct} />
                </td>
                <td className="px-5 py-3.5 text-right">
                  <button
                    type="button"
                    onClick={() => setEditingActual(r)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-blue-600 text-xs font-medium hover:bg-blue-50"
                    title="Cập nhật số ca thực tế"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                    {r.actual_cases !== null ? 'Cập nhật' : 'Nhập thực tế'}
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {editingActual && (
        <ActualCasesDialog
          item={editingActual}
          onClose={() => setEditingActual(null)}
          onSaved={() => {
            setEditingActual(null);
            onUpdated?.();
          }}
        />
      )}
    </div>
  );
}

function DeviationPill({ value }: { value: number | null }) {
  if (value === null || value === undefined) {
    return <span className="text-neutral-400 text-sm">—</span>;
  }
  // Quy ước: predicted > actual → over-forecast (số dương) → màu xanh nếu sai số nhỏ, đỏ nếu lớn.
  const abs = Math.abs(value);
  const sign = value > 0 ? '+' : '';
  const isAccurate = abs <= 5;
  return (
    <span
      className={
        'text-sm font-semibold ' +
        (isAccurate ? 'text-emerald-600' : 'text-red-600')
      }
    >
      {sign}
      {value.toFixed(1)}%
    </span>
  );
}

function ActualCasesDialog({
  item,
  onClose,
  onSaved,
}: {
  item: ForecastHistoryItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [value, setValue] = useState<number>(item.actual_cases ?? 0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (value < 0) {
      setError('Số ca thực tế phải >= 0');
      return;
    }
    setError(null);
    try {
      setSubmitting(true);
      await forecastAnalysisService.updateActual(item.id, value);
      onSaved();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Có lỗi xảy ra');
    } finally {
      setSubmitting(false);
    }
  };

  // Tính trước độ lệch xem trước
  const previewDeviation =
    value > 0
      ? ((item.predicted_cases - value) / value) * 100
      : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">
            Nhập số ca thực tế — Tháng {item.month}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-neutral-50 border border-neutral-100 p-3">
              <p className="text-[11px] text-neutral-500 uppercase">Đã dự báo</p>
              <p className="text-xl font-bold tabular-nums mt-1">
                {item.predicted_cases.toLocaleString('vi-VN')}
              </p>
              <p className="text-[11px] text-neutral-400 mt-0.5">
                {item.disease_label} · {item.region}
              </p>
            </div>
            <div className="rounded-lg bg-blue-50 border border-blue-100 p-3">
              <p className="text-[11px] text-blue-700 uppercase">Sai số dự kiến</p>
              <p
                className={
                  'text-xl font-bold tabular-nums mt-1 ' +
                  (previewDeviation !== null
                    ? Math.abs(previewDeviation) <= 5
                      ? 'text-emerald-700'
                      : 'text-red-700'
                    : 'text-neutral-700')
                }
              >
                {previewDeviation !== null
                  ? `${previewDeviation > 0 ? '+' : ''}${previewDeviation.toFixed(1)}%`
                  : '—'}
              </p>
            </div>
          </div>

          <label className="block">
            <span className="block text-xs font-medium text-neutral-600 mb-1.5">
              Số ca thực tế <span className="text-red-500">*</span>
            </span>
            <input
              type="number"
              required
              min={0}
              value={value}
              onChange={(e) => setValue(Math.max(0, Number(e.target.value)))}
              className="w-full h-10 px-3 rounded-lg border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              autoFocus
            />
          </label>

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
              Lưu số ca thực tế
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
