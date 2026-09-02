import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { AlertTriangle, Filter, Loader2, Trash2 } from 'lucide-react';
import {
  forecastAnalysisService,
  type ForecastHistoryItem,
} from '../../services/forecastAnalysisService';
import { useAuthStore } from '../../store/authStore';

interface Props {
  rows: ForecastHistoryItem[];
  isLoading?: boolean;
  /** Gọi sau khi xoá để nạp lại danh sách. */
  onChanged?: () => void;
}

/** Yêu cầu xác nhận đang chờ: xoá 1 dòng hay xoá sạch. */
type YeuCauXoa =
  | { kieu: 'mot'; row: ForecastHistoryItem }
  | { kieu: 'tatca' };

export default function ForecastHistoryTable({
  rows,
  isLoading,
  onChanged,
}: Props) {
  const { user } = useAuthStore();
  const laQuanTri = user?.role === 'Administrator';

  /** Xoá được khi là người đã ghi nhận bản đó, hoặc là Quản trị viên.
   *  (Backend kiểm tra lại y hệt — đây chỉ là phần hiển thị.) */
  const duocXoa = (r: ForecastHistoryItem) =>
    laQuanTri || (!!r.created_by && r.created_by === user?.username);

  const [xacNhanXoa, setXacNhanXoa] = useState<YeuCauXoa | null>(null);
  const [loiXoa, setLoiXoa] = useState<string | null>(null);

  const xoaMot = useMutation({
    mutationFn: (id: number) => forecastAnalysisService.deleteForecast(id),
    onSuccess: () => {
      setXacNhanXoa(null);
      onChanged?.();
    },
    onError: (err: any) => setLoiXoa(err?.message || 'Không xoá được.'),
  });

  const xoaTatCa = useMutation({
    mutationFn: () => forecastAnalysisService.deleteAllForecasts(),
    onSuccess: () => {
      setXacNhanXoa(null);
      onChanged?.();
    },
    onError: (err: any) => setLoiXoa(err?.message || 'Không xoá được.'),
  });

  const dangXoa = xoaMot.isPending || xoaTatCa.isPending;

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
        <div className="flex items-center gap-1">
          {laQuanTri && rows.length > 0 && (
            <button
              type="button"
              onClick={() => {
                setLoiXoa(null);
                setXacNhanXoa({ kieu: 'tatca' });
              }}
              disabled={dangXoa}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-red-700 bg-red-50 border border-red-200 hover:bg-red-100 disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Xoá toàn bộ
            </button>
          )}
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
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Ghi nhận lúc</th>
              <th className="text-left px-5 py-3 font-medium whitespace-nowrap">Người ghi nhận</th>
              <th className="text-right px-5 py-3 font-medium w-24">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={9} className="py-8">
                  <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tải lịch sử...
                  </div>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-10 text-center text-sm text-neutral-400">
                  Chưa có lịch sử dự báo
                </td>
              </tr>
            ) : filteredRows.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-10 text-center text-sm text-neutral-400">
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
                  <td className="px-5 py-3.5 text-neutral-600 whitespace-nowrap">
                    {formatThoiGian(r.created_at)}
                  </td>
                  <td className="px-5 py-3.5 text-neutral-600 whitespace-nowrap">
                    {r.created_by || '—'}
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button
                      type="button"
                      disabled={!duocXoa(r) || dangXoa}
                      onClick={() => {
                        setLoiXoa(null);
                        setXacNhanXoa({ kieu: 'mot', row: r });
                      }}
                      title={
                        duocXoa(r)
                          ? 'Xoá lần dự báo này'
                          : 'Chỉ người đã ghi nhận hoặc Quản trị viên mới xoá được'
                      }
                      className="inline-flex items-center justify-center w-8 h-8 rounded-lg text-red-600 hover:bg-red-50 disabled:text-neutral-300 disabled:hover:bg-transparent disabled:cursor-not-allowed"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Xác nhận xoá */}
      {xacNhanXoa && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex items-start gap-3 px-5 py-4 border-b border-neutral-100">
              <div className="w-10 h-10 rounded-xl bg-red-50 text-red-600 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-neutral-900 mt-1.5">
                {xacNhanXoa.kieu === 'tatca'
                  ? 'Xoá toàn bộ lịch sử dự báo?'
                  : 'Xoá lần dự báo này?'}
              </h3>
            </div>

            <div className="px-5 py-4 space-y-2 text-sm text-neutral-700">
              {xacNhanXoa.kieu === 'tatca' ? (
                <>
                  <p>
                    Sẽ xoá <span className="font-semibold">{rows.length}</span> bản
                    ghi dự báo của tất cả nhóm bệnh, tỉnh/thành và tháng.
                  </p>
                  <p className="text-neutral-500">
                    Các nhu cầu vật tư đã sinh từ những dự báo này cũng bị xoá theo.
                    Thao tác không hoàn tác được.
                  </p>
                </>
              ) : (
                <>
                  <p>
                    {xacNhanXoa.row.disease_label} · {xacNhanXoa.row.region} · tháng{' '}
                    {xacNhanXoa.row.month} —{' '}
                    <span className="font-semibold">
                      {xacNhanXoa.row.predicted_cases.toLocaleString('vi-VN')}
                    </span>{' '}
                    ca dự báo.
                  </p>
                  <p className="text-neutral-500">Thao tác không hoàn tác được.</p>
                </>
              )}

              {loiXoa && (
                <p className="text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                  {loiXoa}
                </p>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-neutral-100">
              <button
                type="button"
                onClick={() => {
                  setXacNhanXoa(null);
                  setLoiXoa(null);
                }}
                disabled={dangXoa}
                className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-60"
              >
                Huỷ
              </button>
              <button
                type="button"
                disabled={dangXoa}
                onClick={() => {
                  setLoiXoa(null);
                  if (xacNhanXoa.kieu === 'tatca') xoaTatCa.mutate();
                  else xoaMot.mutate(xacNhanXoa.row.id);
                }}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-60"
              >
                {dangXoa ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                {xacNhanXoa.kieu === 'tatca' ? 'Xoá toàn bộ' : 'Xoá'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** ISO → "dd/mm/yyyy hh:mm" theo giờ địa phương; '—' nếu không có. */
function formatThoiGian(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  } catch {
    return '—';
  }
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
