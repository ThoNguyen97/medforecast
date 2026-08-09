import { cn } from '../../utils/cn';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: {
    value: number;
    label: string;
    direction: 'up' | 'down' | 'neutral';
  };
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'neutral';
  className?: string;
}

const colorMap = {
  primary: {
    bg: 'bg-primary-50',
    icon: 'text-primary-600',
    value: 'text-primary-700',
    border: 'border-primary-100',
  },
  success: {
    bg: 'bg-success-50',
    icon: 'text-success-600',
    value: 'text-success-700',
    border: 'border-success-100',
  },
  warning: {
    bg: 'bg-warning-50',
    icon: 'text-warning-600',
    value: 'text-warning-700',
    border: 'border-warning-100',
  },
  danger: {
    bg: 'bg-danger-50',
    icon: 'text-danger-600',
    value: 'text-danger-700',
    border: 'border-danger-100',
  },
  neutral: {
    bg: 'bg-neutral-50',
    icon: 'text-neutral-600',
    value: 'text-neutral-700',
    border: 'border-neutral-100',
  },
};

/**
 * Dashboard metric card displaying a key KPI with optional icon and trend
 */
export default function MetricCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  color = 'primary',
  className,
}: MetricCardProps) {
  const colors = colorMap[color];

  return (
    <div
      className={cn(
        'bg-white rounded-xl border border-neutral-200 shadow-sm p-6',
        className
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-neutral-500 truncate">{title}</p>
          <p className={cn('text-3xl font-bold mt-1 tracking-tight', colors.value)}>
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-neutral-400 mt-1.5">{subtitle}</p>
          )}
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              <span
                className={cn(
                  'text-xs font-medium',
                  trend.direction === 'up' && 'text-success-600',
                  trend.direction === 'down' && 'text-danger-600',
                  trend.direction === 'neutral' && 'text-neutral-500'
                )}
              >
                {trend.direction === 'up' ? '↑' : trend.direction === 'down' ? '↓' : '→'}{' '}
                {trend.value}%
              </span>
              <span className="text-xs text-neutral-400">{trend.label}</span>
            </div>
          )}
        </div>
        <div
          className={cn(
            'flex items-center justify-center w-12 h-12 rounded-xl ml-4 shrink-0',
            colors.bg
          )}
        >
          <div className={colors.icon}>{icon}</div>
        </div>
      </div>
    </div>
  );
}
