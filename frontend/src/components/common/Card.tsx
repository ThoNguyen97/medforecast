import { cn } from '../../utils/cn';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hover?: boolean;
}

const paddingClasses = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
};

export default function Card({
  children,
  className,
  padding = 'md',
  hover = false,
}: CardProps) {
  return (
    <div
      className={cn(
        'bg-white rounded-xl border border-neutral-200 shadow-card',
        hover && 'hover:shadow-card-hover transition-shadow duration-200 cursor-pointer',
        paddingClasses[padding],
        className
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
}

export function CardHeader({ title, subtitle, action, className }: CardHeaderProps) {
  return (
    <div className={cn('flex items-start justify-between mb-4', className)}>
      <div>
        <h3 className="text-base font-semibold text-neutral-900">{title}</h3>
        {subtitle && (
          <p className="text-sm text-neutral-500 mt-0.5">{subtitle}</p>
        )}
      </div>
      {action && <div className="ml-4 shrink-0">{action}</div>}
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: {
    value: number;
    label: string;
    direction: 'up' | 'down' | 'neutral';
  };
  color?: 'primary' | 'success' | 'warning' | 'danger' | 'neutral';
  className?: string;
}

const colorMap = {
  primary: { bg: 'bg-primary-50', icon: 'text-primary-600', value: 'text-primary-700' },
  success: { bg: 'bg-success-50', icon: 'text-success-600', value: 'text-success-700' },
  warning: { bg: 'bg-warning-50', icon: 'text-warning-600', value: 'text-warning-700' },
  danger: { bg: 'bg-danger-50', icon: 'text-danger-600', value: 'text-danger-700' },
  neutral: { bg: 'bg-neutral-50', icon: 'text-neutral-600', value: 'text-neutral-700' },
};

export function MetricCard({
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
    <Card className={cn('', className)}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-neutral-500 truncate">{title}</p>
          <p className={cn('text-2xl font-bold mt-1', colors.value)}>{value}</p>
          {subtitle && (
            <p className="text-xs text-neutral-400 mt-1">{subtitle}</p>
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
        {icon && (
          <div className={cn('flex items-center justify-center w-12 h-12 rounded-xl ml-4 shrink-0', colors.bg)}>
            <div className={colors.icon}>{icon}</div>
          </div>
        )}
      </div>
    </Card>
  );
}
