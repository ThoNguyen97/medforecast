import { CheckCircle, AlertTriangle, AlertOctagon, Info, Package, Calendar, TrendingDown } from 'lucide-react';
import { cn } from '../../utils/cn';
import Button from '../common/Button';
import type { Alert, AlertSeverity } from '../../types/alerts';
import { ALERT_SEVERITY_LABELS, ALERT_TYPE_LABELS } from '../../types/alerts';

interface AlertCardProps {
  alert: Alert;
  onResolve: (id: number) => void;
  isResolving?: boolean;
}

const severityConfig: Record<
  AlertSeverity,
  {
    borderColor: string;
    bgColor: string;
    badgeBg: string;
    badgeText: string;
    dotColor: string;
    icon: React.ReactNode;
    iconColor: string;
  }
> = {
  critical: {
    borderColor: 'border-l-red-500',
    bgColor: 'bg-red-50/40',
    badgeBg: 'bg-red-100',
    badgeText: 'text-red-700',
    dotColor: 'bg-red-500',
    icon: <AlertOctagon className="w-5 h-5" />,
    iconColor: 'text-red-500',
  },
  high: {
    borderColor: 'border-l-orange-500',
    bgColor: 'bg-orange-50/40',
    badgeBg: 'bg-orange-100',
    badgeText: 'text-orange-700',
    dotColor: 'bg-orange-500',
    icon: <AlertTriangle className="w-5 h-5" />,
    iconColor: 'text-orange-500',
  },
  medium: {
    borderColor: 'border-l-yellow-500',
    bgColor: 'bg-yellow-50/40',
    badgeBg: 'bg-yellow-100',
    badgeText: 'text-yellow-700',
    dotColor: 'bg-yellow-500',
    icon: <Info className="w-5 h-5" />,
    iconColor: 'text-yellow-600',
  },
};

function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const config = severityConfig[severity];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
        config.badgeBg,
        config.badgeText
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', config.dotColor)} />
      {ALERT_SEVERITY_LABELS[severity]}
    </span>
  );
}

export default function AlertCard({ alert, onResolve, isResolving }: AlertCardProps) {
  const config = severityConfig[alert.severity];
  const isResolved = alert.is_resolved;

  return (
    <div
      className={cn(
        'bg-white border border-neutral-200 rounded-xl border-l-4 shadow-card overflow-hidden',
        isResolved ? 'border-l-neutral-300 opacity-70' : config.borderColor,
        !isResolved && alert.severity === 'critical' && 'ring-1 ring-red-100'
      )}
    >
      {/* Top highlight bar for critical alerts */}
      {!isResolved && alert.severity === 'critical' && (
        <div className="bg-red-500 text-white text-xs font-semibold px-4 py-1 flex items-center gap-1.5">
          <AlertOctagon className="w-3.5 h-3.5" />
          Cảnh báo Nghiêm trọng — Cần xử lý ngay
        </div>
      )}

      <div className={cn('p-4', !isResolved && config.bgColor)}>
        <div className="flex items-start justify-between gap-3">
          {/* Left: icon + severity indicator */}
          <div className={cn('mt-0.5 shrink-0', isResolved ? 'text-neutral-400' : config.iconColor)}>
            {isResolved ? <CheckCircle className="w-5 h-5" /> : config.icon}
          </div>

          {/* Center: main content */}
          <div className="flex-1 min-w-0">
            {/* Header row */}
            <div className="flex flex-wrap items-center gap-2 mb-1.5">
              <span className="font-semibold text-neutral-900 text-sm truncate">
                {alert.supply_name}
              </span>
              {isResolved ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-neutral-100 text-neutral-500">
                  <CheckCircle className="w-3 h-3" />
                  Đã xử lý
                </span>
              ) : (
                <SeverityBadge severity={alert.severity} />
              )}
              <span className="text-xs text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded-full">
                {ALERT_TYPE_LABELS[alert.alert_type] ?? alert.alert_type}
              </span>
            </div>

            {/* Message */}
            {alert.message && (
              <p className="text-sm text-neutral-600 mb-3">{alert.message}</p>
            )}

            {/* Stats row */}
            <div className="flex flex-wrap gap-4 text-xs text-neutral-500">
              {alert.current_stock !== null && (
                <div className="flex items-center gap-1">
                  <Package className="w-3.5 h-3.5" />
                  <span>Tồn kho hiện tại:</span>
                  <span className="font-semibold text-neutral-700">
                    {alert.current_stock.toLocaleString()}
                  </span>
                </div>
              )}
              {alert.required_stock !== null && (
                <div className="flex items-center gap-1">
                  <TrendingDown className="w-3.5 h-3.5" />
                  <span>Cần thiết:</span>
                  <span className="font-semibold text-neutral-700">
                    {alert.required_stock.toLocaleString()}
                  </span>
                </div>
              )}
              {alert.shortage_date && (
                <div className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-red-400" />
                  <span>Ngày thiếu hụt dự kiến:</span>
                  <span className={cn('font-semibold', isResolved ? 'text-neutral-500' : 'text-red-600')}>
                    {new Date(alert.shortage_date).toLocaleDateString('vi-VN', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </span>
                </div>
              )}
              <div className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                <span>Tạo lúc:</span>
                <span className="text-neutral-500">
                  {new Date(alert.created_at).toLocaleDateString('vi-VN', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            </div>
          </div>

          {/* Right: action */}
          {!isResolved && (
            <div className="shrink-0">
              <Button
                variant="success"
                size="sm"
                onClick={() => onResolve(alert.id)}
                isLoading={isResolving}
                className="whitespace-nowrap"
              >
                <CheckCircle className="w-3.5 h-3.5 mr-1" />
                Nhập vào tồn kho
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
