import { cn } from '../../utils/cn';
import type { AlertLevel } from '../../types/dashboardV2';

interface Props {
  counts: Record<AlertLevel, number>;
  redDays: number | null;
  amberDays: number | null;
}

/**
 * Thẻ tóm tắt trang Quản lý thuốc — CÙNG số với trang Cảnh báo (toàn danh mục).
 *
 * Bốn ô nhãn, mỗi ô nói rõ ngưỡng và ý nghĩa vận hành của màu đó, để người
 * đọc không phải đoán "Xám" là gì. Xám KHÔNG phải an toàn: là mã có tiêu hao
 * nhưng không có dòng tồn kho nên không tính được DOI.
 */
export default function InventoryAlertCard({
  counts,
  redDays,
  amberDays,
}: Props) {
  const red = redDays ?? 18;
  const amber = amberDays ?? 36;

  const O: Array<{
    level: AlertLevel;
    ten: string;
    nguong: string;
    nghia: string;
    dot: string;
    box: string;
    so: string;
  }> = [
    {
      level: 'red',
      ten: 'Đỏ',
      nguong: `DOI ≤ ${red} ngày`,
      nghia: 'Sắp hết, cần nhập ngay.',
      dot: 'bg-[#d03b3b]',
      box: 'border-red-100 bg-red-50/60',
      so: 'text-red-700',
    },
    {
      level: 'amber',
      ten: 'Vàng',
      nguong: `${red} < DOI ≤ ${amber} ngày`,
      nghia: 'Còn dùng được, cần theo dõi.',
      dot: 'bg-[#fab219]',
      box: 'border-amber-100 bg-amber-50/60',
      so: 'text-amber-800',
    },
    {
      level: 'green',
      ten: 'Xanh',
      nguong: `DOI > ${amber} ngày`,
      nghia: 'Tồn đủ.',
      dot: 'bg-[#0ca30c]',
      box: 'border-emerald-100 bg-emerald-50/60',
      so: 'text-emerald-700',
    },
    {
      level: 'grey',
      ten: 'Xám',
      nguong: 'Không tính được DOI',
      nghia: 'Chưa có số tồn kho.',
      dot: 'bg-[#898781]',
      box: 'border-neutral-200 bg-neutral-50',
      so: 'text-neutral-700',
    },
  ];

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      {/* Bốn ô nhãn — mỗi ô: tên · số · ngưỡng · chú thích. Không có số tổng
          riêng: Đỏ + Vàng đã nằm ở hai ô đầu, số "cần chú ý" thuộc về Tổng quan
          và Cảnh báo thiếu hụt. */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-2.5">
          {O.map((o) => (
            <div
              key={o.level}
              className={cn('rounded-xl border px-3 py-2.5', o.box)}
              title={o.nghia}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-neutral-700">
                  <span className={cn('w-2 h-2 rounded-full', o.dot)} />
                  {o.ten}
                </span>
                <span className={cn('text-lg font-extrabold tabular-nums leading-none', o.so)}>
                  {counts[o.level].toLocaleString('vi-VN')}
                </span>
              </div>
              <p className="text-[11px] font-medium text-neutral-600 mt-1.5">{o.nguong}</p>
              <p className="text-[11px] text-neutral-500 leading-snug mt-0.5">{o.nghia}</p>
            </div>
          ))}
      </div>
    </div>
  );
}
