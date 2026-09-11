import { cn } from '../../utils/cn';
import { LEVEL_LABELS, type AlertLevel } from '../../types/dashboardV2';

/**
 * Nhãn bốn mức theo DOI. Màu đi kèm chấm + chữ, không bao giờ chỉ có màu.
 * Xám là "chưa đo được" — không phải an toàn.
 */
const STYLE: Record<AlertLevel, { pill: string; dot: string }> = {
  red: { pill: 'bg-red-50 text-red-700 border-red-100', dot: 'bg-[#d03b3b]' },
  amber: { pill: 'bg-amber-50 text-amber-800 border-amber-100', dot: 'bg-[#fab219]' },
  green: { pill: 'bg-emerald-50 text-emerald-700 border-emerald-100', dot: 'bg-[#0ca30c]' },
  grey: { pill: 'bg-neutral-100 text-neutral-600 border-neutral-200', dot: 'bg-[#898781]' },
};

export const LEVEL_HEX: Record<AlertLevel, string> = {
  red: '#d03b3b',
  amber: '#fab219',
  green: '#0ca30c',
  grey: '#898781',
};

export default function LevelPill({
  level,
  label,
  className,
}: {
  level: AlertLevel;
  label?: string;
  className?: string;
}) {
  const s = STYLE[level];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[11px] font-semibold whitespace-nowrap',
        s.pill,
        className,
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full', s.dot)} />
      {label ?? LEVEL_LABELS[level]}
    </span>
  );
}
