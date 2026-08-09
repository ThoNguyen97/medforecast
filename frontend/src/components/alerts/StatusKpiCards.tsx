import { AlertTriangle, Bell, CheckCircle2, Archive } from 'lucide-react';
import { cn } from '../../utils/cn';

export type StockClass = 'critical' | 'warning' | 'safe' | 'overstock';

const CARD_META: Record<
  StockClass,
  {
    label: string;
    sub: string;
    icon: React.ComponentType<{ className?: string }>;
    bgRing: string;
    bgIcon: string;
    iconColor: string;
    valueColor: string;
  }
> = {
  critical: {
    label: 'NGUY HIỂM',
    sub: '(CẠN KIỆT)',
    icon: AlertTriangle,
    bgRing: 'bg-red-50/80 border-red-100',
    bgIcon: 'bg-red-100',
    iconColor: 'text-red-600',
    valueColor: 'text-red-600',
  },
  warning: {
    label: 'CẢNH BÁO',
    sub: '(SẮP HẾT)',
    icon: Bell,
    bgRing: 'bg-amber-50/70 border-amber-100',
    bgIcon: 'bg-amber-100',
    iconColor: 'text-amber-600',
    valueColor: 'text-amber-600',
  },
  safe: {
    label: 'AN TOÀN',
    sub: '(ĐỦ DÙNG)',
    icon: CheckCircle2,
    bgRing: 'bg-emerald-50/70 border-emerald-100',
    bgIcon: 'bg-emerald-100',
    iconColor: 'text-emerald-600',
    valueColor: 'text-emerald-600',
  },
  overstock: {
    label: 'DƯ TỒN',
    sub: '(CẦN XEM XÉT)',
    icon: Archive,
    bgRing: 'bg-neutral-50 border-neutral-200',
    bgIcon: 'bg-neutral-100',
    iconColor: 'text-neutral-600',
    valueColor: 'text-neutral-700',
  },
};

interface Props {
  counts: Record<StockClass, number>;
  active: StockClass | 'all';
  onSelect: (key: StockClass | 'all') => void;
}

export default function StatusKpiCards({ counts, active, onSelect }: Props) {
  const order: StockClass[] = ['critical', 'warning', 'safe', 'overstock'];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {order.map((key) => {
        const meta = CARD_META[key];
        const Icon = meta.icon;
        const isActive = active === key;
        return (
          <button
            type="button"
            key={key}
            onClick={() => onSelect(isActive ? 'all' : key)}
            className={cn(
              'relative text-left rounded-2xl border p-4 transition',
              meta.bgRing,
              isActive
                ? 'ring-2 ring-blue-500/60 shadow-sm'
                : 'hover:shadow-card-hover hover:-translate-y-0.5',
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[11px] font-bold tracking-wide text-neutral-700 uppercase">
                  {meta.label}
                </p>
                <p className="text-[11px] font-medium text-neutral-500 -mt-0.5">
                  {meta.sub}
                </p>
              </div>
              <span
                className={cn(
                  'w-9 h-9 rounded-xl flex items-center justify-center',
                  meta.bgIcon,
                )}
              >
                <Icon className={cn('w-4 h-4', meta.iconColor)} />
              </span>
            </div>
            <p className={cn('text-3xl font-extrabold tabular-nums mt-3', meta.valueColor)}>
              {counts[key].toLocaleString('vi-VN')}
            </p>
          </button>
        );
      })}
    </div>
  );
}
