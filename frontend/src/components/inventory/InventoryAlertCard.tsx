import { AlertTriangle } from 'lucide-react';
import LevelPill from '../dashboard/LevelPill';
import type { AlertLevel } from '../../types/dashboardV2';

interface Props {
  counts: Record<AlertLevel, number>;
  measured: number;        // số mã đo được DOI (có tiêu hao 12 kỳ đã chốt)
  catalogue: number;       // toàn danh mục thuốc trong medical_supplies
  stockSource: string | null;
  redDays: number | null;
  amberDays: number | null;
}

/**
 * Thẻ tóm tắt trang Quản lý thuốc — CÙNG số với trang Cảnh báo (toàn danh mục).
 * Trước 13/09/2026 thẻ này đếm "Vật tư sắp hết" theo `safety_stock`, cột chỉ
 * có giá trị ở 34/5.051 dòng, nên luôn hiện "0 mục" trong khi Cảnh báo báo Đỏ.
 */
export default function InventoryAlertCard({
  counts,
  measured,
  catalogue,
  stockSource,
  redDays,
  amberDays,
}: Props) {
  const canChuY = counts.red + counts.amber;
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex flex-wrap items-start gap-5">
        <div className="flex items-start gap-3 min-w-[240px]">
          <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-5 h-5 text-red-600" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-neutral-500 font-semibold">
              Thuốc cần chú ý (Đỏ + Vàng)
            </p>
            <p className="text-3xl font-extrabold text-red-600 mt-1 tabular-nums">
              {canChuY.toLocaleString('vi-VN')}{' '}
              <span className="text-base font-medium text-neutral-500">
                / {measured.toLocaleString('vi-VN')} mã đo được
              </span>
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 self-center">
          {(['red', 'amber', 'green', 'grey'] as AlertLevel[]).map((lv) => (
            <span key={lv} className="inline-flex items-center gap-1.5 text-sm text-neutral-700">
              <LevelPill level={lv} />
              <span className="font-semibold tabular-nums">
                {counts[lv].toLocaleString('vi-VN')}
              </span>
            </span>
          ))}
        </div>
      </div>

      <p className="text-xs text-neutral-500 mt-3">
        DOI = tồn hữu dụng (FEFO) / tiêu hao ngày
        {redDays != null && amberDays != null && (
          <> · Đỏ ≤ {redDays} · Vàng ≤ {amberDays} ngày</>
        )}
        {stockSource && <> · Nguồn tồn: {stockSource}</>}
        {' '}· Danh mục {catalogue.toLocaleString('vi-VN')} mã, trong đó{' '}
        {(catalogue - measured).toLocaleString('vi-VN')} mã không có tiêu hao trong 12 kỳ đã
        chốt nên không đo được DOI (ẩn mặc định).
      </p>
    </div>
  );
}
