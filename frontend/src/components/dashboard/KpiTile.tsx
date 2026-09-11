import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { cn } from '../../utils/cn';

/**
 * Thẻ KPI của Dashboard. Số lớn + nhãn + một dòng ngữ cảnh + chân thẻ.
 * `tone` chỉ tô một dải mảnh bên trái — không đổ màu cả thẻ để năm thẻ
 * đứng cạnh nhau vẫn đọc như một hàng.
 */
export type KpiTone = 'neutral' | 'blue' | 'red' | 'amber' | 'green';

const STRIPE: Record<KpiTone, string> = {
  neutral: 'bg-neutral-300',
  blue: 'bg-[#2a78d6]',
  red: 'bg-[#d03b3b]',
  amber: 'bg-[#fab219]',
  green: 'bg-[#0ca30c]',
};

export default function KpiTile({
  label,
  value,
  unit,
  context,
  footer,
  tone = 'neutral',
  to,
  loading,
  className,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  context?: ReactNode;
  footer?: ReactNode;
  tone?: KpiTone;
  to?: string;
  loading?: boolean;
  className?: string;
}) {
  const navigate = useNavigate();
  const interactive = !!to;
  const go = () => {
    if (to) navigate(to);
  };
  return (
    <div
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={interactive ? go : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                go();
              }
            }
          : undefined
      }
      className={cn(
        'relative bg-white rounded-2xl border border-neutral-200 pl-5 pr-4 py-4 min-h-[128px] flex flex-col overflow-hidden',
        interactive &&
          'cursor-pointer transition hover:shadow-card-hover hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-blue-500/40',
        className,
      )}
    >
      <span className={cn('absolute left-0 top-4 bottom-4 w-1 rounded-r', STRIPE[tone])} />
      <p className="text-[11px] uppercase tracking-wider text-neutral-500 font-semibold">{label}</p>
      {loading ? (
        <div className="mt-2 h-9 w-24 rounded bg-neutral-100 animate-pulse" />
      ) : (
        <p className="mt-1.5 text-[30px] leading-none font-extrabold text-neutral-900 tabular-nums">
          {value}
          {unit && <span className="ml-1.5 text-sm font-medium text-neutral-400">{unit}</span>}
        </p>
      )}
      {context && <div className="mt-2 text-xs text-neutral-600 leading-snug">{context}</div>}
      {footer && <div className="mt-auto pt-2 text-[11px] text-neutral-500 leading-snug">{footer}</div>}
    </div>
  );
}
