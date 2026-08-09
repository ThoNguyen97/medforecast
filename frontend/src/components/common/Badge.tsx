import { cn } from '../../utils/cn';

type BadgeVariant = 'primary' | 'success' | 'warning' | 'danger' | 'neutral' | 'info';
type BadgeSize = 'sm' | 'md';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  primary: 'bg-primary-100 text-primary-700 border-primary-200',
  success: 'bg-success-100 text-success-700 border-success-200',
  warning: 'bg-warning-100 text-warning-700 border-warning-200',
  danger: 'bg-danger-100 text-danger-700 border-danger-200',
  neutral: 'bg-neutral-100 text-neutral-600 border-neutral-200',
  info: 'bg-blue-100 text-blue-700 border-blue-200',
};

const dotColorClasses: Record<BadgeVariant, string> = {
  primary: 'bg-primary-500',
  success: 'bg-success-500',
  warning: 'bg-warning-500',
  danger: 'bg-danger-500',
  neutral: 'bg-neutral-400',
  info: 'bg-blue-500',
};

const sizeClasses: Record<BadgeSize, string> = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
};

export default function Badge({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-medium rounded-full border',
        variantClasses[variant],
        sizeClasses[size],
        className
      )}
    >
      {dot && (
        <span
          className={cn('w-1.5 h-1.5 rounded-full shrink-0', dotColorClasses[variant])}
        />
      )}
      {children}
    </span>
  );
}

// Convenience components for common use cases
export function StockStatusBadge({ status }: { status: 'safe' | 'low' | 'critical' }) {
  const config = {
    safe: { variant: 'success' as BadgeVariant, label: 'An toàn' },
    low: { variant: 'warning' as BadgeVariant, label: 'Thấp' },
    critical: { variant: 'danger' as BadgeVariant, label: 'Nguy hiểm' },
  };
  const { variant, label } = config[status];
  return <Badge variant={variant} dot>{label}</Badge>;
}

export function AlertSeverityBadge({ severity }: { severity: 'critical' | 'high' | 'medium' | 'low' }) {
  const config = {
    critical: { variant: 'danger' as BadgeVariant, label: 'Nghiêm trọng' },
    high: { variant: 'warning' as BadgeVariant, label: 'Cao' },
    medium: { variant: 'info' as BadgeVariant, label: 'Trung bình' },
    low: { variant: 'neutral' as BadgeVariant, label: 'Thấp' },
  };
  const { variant, label } = config[severity];
  return <Badge variant={variant} dot>{label}</Badge>;
}
