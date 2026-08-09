import { cn } from '../../utils/cn';

type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
type SpinnerColor = 'primary' | 'white' | 'neutral';

interface LoadingSpinnerProps {
  size?: SpinnerSize;
  color?: SpinnerColor;
  className?: string;
  label?: string;
}

const sizeClasses: Record<SpinnerSize, string> = {
  xs: 'w-3 h-3 border',
  sm: 'w-4 h-4 border-2',
  md: 'w-6 h-6 border-2',
  lg: 'w-8 h-8 border-2',
  xl: 'w-12 h-12 border-4',
};

const colorClasses: Record<SpinnerColor, string> = {
  primary: 'border-primary-200 border-t-primary-600',
  white: 'border-white/30 border-t-white',
  neutral: 'border-neutral-200 border-t-neutral-600',
};

export default function LoadingSpinner({
  size = 'md',
  color = 'primary',
  className,
  label,
}: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      className={cn('inline-flex items-center gap-2', className)}
    >
      <div
        className={cn(
          'rounded-full animate-spin',
          sizeClasses[size],
          colorClasses[color]
        )}
      />
      {label && (
        <span className="text-sm text-neutral-600">{label}</span>
      )}
      <span className="sr-only">Đang tải...</span>
    </div>
  );
}

// Full-page loading overlay
export function PageLoader({ label = 'Đang tải...' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <LoadingSpinner size="xl" label={label} />
    </div>
  );
}
