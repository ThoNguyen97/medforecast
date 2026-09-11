import { useNavigate } from 'react-router-dom';
import { ROUTES } from '../../utils/constants';
import LevelPill from './LevelPill';
import { GREY_REASON_LABELS, type AlertRow } from '../../types/dashboardV2';

const fmt = (v: number | null | undefined, digits = 0) =>
  v == null ? '—' : v.toLocaleString('vi-VN', { maximumFractionDigits: digits });

/**
 * Bảng cảnh báo theo DOI. Cột "Thiếu hụt dự kiến" = Δ_need trên horizon —
 * để trống (không phải 0) khi Tầng 2 chưa chạy vì chưa có dự báo.
 */
export default function AlertsTable({
  rows,
  demandReady,
  horizonDays,
  loading,
}: {
  rows: AlertRow[];
  demandReady: boolean;
  horizonDays: number;
  loading?: boolean;
}) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="px-5 pb-5 space-y-2">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-9 rounded bg-neutral-100 animate-pulse" />
        ))}
      </div>
    );
  }
  if (rows.length === 0) {
    return <div className="py-10 text-center text-sm text-neutral-400">Không có mã nào ở mức đã chọn.</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-neutral-500 text-[11px] uppercase tracking-wide">
            <th className="text-left px-5 py-2.5 font-semibold">Vật tư</th>
            <th className="text-left px-3 py-2.5 font-semibold">Danh mục</th>
            <th className="text-right px-3 py-2.5 font-semibold">Tồn hữu dụng</th>
            <th className="text-right px-3 py-2.5 font-semibold">Nhu cầu/ngày</th>
            <th className="text-right px-3 py-2.5 font-semibold">DOI</th>
            <th className="text-right px-3 py-2.5 font-semibold" title={`Δ = max(0, nhu cầu ${horizonDays} ngày − tồn hữu dụng)`}>
              Thiếu hụt dự kiến
            </th>
            <th className="text-left px-5 py-2.5 font-semibold">Mức</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.supply_code}
              onClick={() => navigate(ROUTES.ALERTS)}
              className="border-t border-neutral-100 hover:bg-neutral-50 cursor-pointer"
            >
              <td className="px-5 py-2.5">
                <div className="font-medium text-neutral-900 leading-tight">{r.ten}</div>
                <div className="text-[11px] text-neutral-500 font-mono">
                  {r.supply_code}
                  {r.don_vi ? ` · ${r.don_vi}` : ''}
                  {r.fefo_ap_dung ? '' : ' · chưa FEFO'}
                </div>
              </td>
              <td className="px-3 py-2.5 text-neutral-600">{r.danh_muc}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {fmt(r.s_usable)}
                {r.s_expiring > 0 && (
                  <span className="block text-[10px] text-amber-700">−{fmt(r.s_expiring)} sắp hết hạn</span>
                )}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums text-neutral-600">{fmt(r.d_daily, 1)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums font-semibold">
                {r.doi == null ? '—' : `${fmt(r.doi, 1)} ng`}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {!demandReady ? (
                  <span className="text-neutral-400" title="Chưa có dự báo kỳ tới">đang tính</span>
                ) : r.delta_need == null ? (
                  '—'
                ) : r.delta_need > 0 ? (
                  <span className="text-red-700 font-semibold">{fmt(r.delta_need)}</span>
                ) : (
                  <span className="text-neutral-400">0</span>
                )}
              </td>
              <td className="px-5 py-2.5">
                <LevelPill level={r.muc} label={r.muc === 'grey' && r.ly_do_xam ? GREY_REASON_LABELS[r.ly_do_xam] : undefined} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
