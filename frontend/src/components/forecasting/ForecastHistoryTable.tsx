import { useState } from 'react';
import { Filter, Loader2 } from 'lucide-react';
import type { ForecastHistoryItem } from '../../services/forecastAnalysisService';

interface Props {
  rows: ForecastHistoryItem[];
  isLoading?: boolean;
}

export default function ForecastHistoryTable({ rows, isLoading }: Props) {
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
                Nhóm bệnh
              </span>
              <select
                value={filterDisease}
                onChange={(e) => setFilterDisease(e.target.value)}
                className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              >
                <option value="all">Tất cả nhóm bệnh</option>
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

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-xs border-y border-neutral-100">
              {/* Ba cột đầu là khóa của một lần dự báo */}
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Tháng dự báo</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Nhóm bệnh</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Tỉnh/Thành phố</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Số ca dự báo</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Số ca thực tế</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Độ lệch</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="py-8">
                  <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tải lịch sử...
                  </div>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-10 text-center text-sm text-neutral-400">
                  Chưa có lịch sử dự báo
                </td>
              </tr>
            ) : filteredRows.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-10 text-center text-sm text-neutral-400">
                  Không tìm thấy kết quả phù hợp với bộ lọc
                </td>
              </tr>
            ) : (
              filteredRows.map((r) => (
                <tr key={r.id} className="border-t border-neutral-100">
                  <td className="px-5 py-3.5 text-neutral-700 whitespace-nowrap">
                    Tháng {r.month}
                  </td>
                  <td className="px-5 py-3.5 text-neutral-700">{r.disease_label}</td>
                  <td className="px-5 py-3.5 text-neutral-700">{r.region}</td>
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
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
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
