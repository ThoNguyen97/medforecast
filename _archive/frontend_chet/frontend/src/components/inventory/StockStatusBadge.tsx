import { cn } from '../../utils/cn';

export type StockStatus = 'safe' | 'low' | 'critical';

interface StockStatusBadgeProps {
  status: StockStatus;
  className?: string;
}

const statusConfig = {
  safe: {
    label: 'An toàn',
    className: 'bg-green-50 text-green-700 border-green-200',
  },
  low: {
    label: 'Sắp hết',
    className: 'bg-yellow-50 text-yellow-700 border-yellow-200',
  },
  critical: {
    label: 'Nguy cơ',
    className: 'bg-red-50 text-red-700 border-red-200',
  },
};

export default function StockStatusBadge({ status, className }: StockStatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.safe;

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border',
        config.className,
        className
      )}
    >
      {config.label}
    </span>
  );
}
