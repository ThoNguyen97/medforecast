import { BellOff } from 'lucide-react';
import AlertCard from './AlertCard';
import LoadingSpinner from '../common/LoadingSpinner';
import type { Alert } from '../../types/alerts';

interface AlertsListProps {
  alerts: Alert[];
  isLoading?: boolean;
  resolvingId: number | null;
  onResolve: (id: number) => void;
}

export default function AlertsList({
  alerts,
  isLoading,
  resolvingId,
  onResolve,
}: AlertsListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-neutral-400">
        <BellOff className="w-10 h-10" />
        <p className="text-sm font-medium">Không có cảnh báo nào</p>
        <p className="text-xs">Tất cả vật tư đang ở mức an toàn</p>
      </div>
    );
  }

  // Sort: critical first, then high, then medium; unresolved before resolved
  const sorted = [...alerts].sort((a, b) => {
    if (a.is_resolved !== b.is_resolved) {
      return a.is_resolved ? 1 : -1;
    }
    const severityOrder = { critical: 0, high: 1, medium: 2 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });

  return (
    <div className="space-y-3">
      {/* Unresolved alerts */}
      {sorted.filter(a => !a.is_resolved).length > 0 && (
        <div className="text-xs font-semibold text-red-600 uppercase tracking-wide px-1">
          Chưa xử lý ({sorted.filter(a => !a.is_resolved).length})
        </div>
      )}
      {sorted.filter(a => !a.is_resolved).map((alert) => (
        <AlertCard
          key={alert.id}
          alert={alert}
          onResolve={onResolve}
          isResolving={resolvingId === alert.id}
        />
      ))}
      
      {/* Resolved alerts */}
      {sorted.filter(a => a.is_resolved).length > 0 && (
        <>
          <div className="text-xs font-semibold text-green-600 uppercase tracking-wide px-1 pt-4 border-t">
            ✓ Đã xử lý ({sorted.filter(a => a.is_resolved).length})
          </div>
          {sorted.filter(a => a.is_resolved).map((alert) => (
            <div key={alert.id} className="opacity-60">
              <AlertCard
                alert={alert}
                onResolve={onResolve}
                isResolving={resolvingId === alert.id}
              />
            </div>
          ))}
        </>
      )}
    </div>
  );
}
