import { cn } from '../../utils/cn';

export type InventoryStatus = 'normal' | 'low' | 'critical';

const STATUS_CFG: Record<
  InventoryStatus,
  { label: string; bg: string; text: string; dot: string }
> = {
  normal: {
    label: 'BÌNH THƯỜNG',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    dot: 'bg-emerald-500',
  },
  low: {
    label: 'DƯỚI NGƯỠNG',
    bg: 'bg-amber-50',
    text: 'text-amber-700',
    dot: 'bg-amber-500',
  },
  critical: {
    label: 'CẦN NHẬP GẤP',
    bg: 'bg-red-50',
    text: 'text-red-700',
    dot: 'bg-red-500',
  },
};

export default function InventoryStatusBadge({
  status,
}: {
  status: InventoryStatus;
}) {
  const cfg = STATUS_CFG[status];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold',
        cfg.bg,
        cfg.text,
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', cfg.dot)} />
      {cfg.label}
    </span>
  );
}

export function classifyStatus(
  currentStock: number,
  safetyStock: number,
): InventoryStatus {
  // Chưa thiết lập ngưỡng AT (= 0) → coi như chưa quản lý ngưỡng,
  // không đánh dấu nguy hiểm. Logic này khớp với /alerts: khi
  // safety_stock = 0 và không có nhu cầu dự báo thì suggested_import = 0,
  // tức không cần nhập.
  if (safetyStock <= 0) return 'normal';

  // Có AT mà tồn = 0 hoặc dưới 30% AT → cần nhập gấp.
  if (currentStock <= 0) return 'critical';
  if (currentStock < safetyStock * 0.3) return 'critical';
  // Tồn dưới ngưỡng nhưng chưa nguy hiểm.
  if (currentStock <= safetyStock) return 'low';
  return 'normal';
}
