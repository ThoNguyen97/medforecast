import { AlertOctagon, AlertTriangle, Info, CheckCircle } from 'lucide-react';
import type { Alert } from '../../types/alerts';

interface AlertsStatsProps {
  alerts: Alert[];
}

export default function AlertsStats({ alerts }: AlertsStatsProps) {
  const active = alerts.filter((a) => !a.is_resolved);
  const resolved = alerts.filter((a) => a.is_resolved);
  const critical = active.filter((a) => a.severity === 'critical');
  const high = active.filter((a) => a.severity === 'high');
  const medium = active.filter((a) => a.severity === 'medium');

  const stats = [
    {
      label: 'Nghiêm trọng',
      value: critical.length,
      icon: <AlertOctagon className="w-5 h-5" />,
      bg: 'bg-red-50',
      iconColor: 'text-red-500',
      valueColor: 'text-red-700',
      borderColor: 'border-red-200',
    },
    {
      label: 'Mức cao',
      value: high.length,
      icon: <AlertTriangle className="w-5 h-5" />,
      bg: 'bg-orange-50',
      iconColor: 'text-orange-500',
      valueColor: 'text-orange-700',
      borderColor: 'border-orange-200',
    },
    {
      label: 'Trung bình',
      value: medium.length,
      icon: <Info className="w-5 h-5" />,
      bg: 'bg-yellow-50',
      iconColor: 'text-yellow-600',
      valueColor: 'text-yellow-700',
      borderColor: 'border-yellow-200',
    },
    {
      label: 'Đã xử lý',
      value: resolved.length,
      icon: <CheckCircle className="w-5 h-5" />,
      bg: 'bg-success-50',
      iconColor: 'text-success-600',
      valueColor: 'text-success-700',
      borderColor: 'border-success-200',
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className={`${stat.bg} border ${stat.borderColor} rounded-xl p-4 flex items-center gap-3`}
        >
          <div className={`${stat.iconColor} shrink-0`}>{stat.icon}</div>
          <div>
            <p className={`text-2xl font-bold ${stat.valueColor}`}>{stat.value}</p>
            <p className="text-xs text-neutral-500 mt-0.5">{stat.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
