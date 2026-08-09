import { useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowRight } from 'lucide-react';
import Card, { CardHeader } from '../common/Card';
import { AlertSeverityBadge } from '../common/Badge';
import Button from '../common/Button';
import type { DashboardCriticalAlert } from '../../types/dashboard';
import { formatDate } from '../../utils/formatters';
import { ROUTES } from '../../utils/constants';

interface CriticalAlertsTableProps {
  alerts: DashboardCriticalAlert[];
}

/**
 * Table of top critical alerts shown on the dashboard.
 * Displays supply name, severity badge, shortage date, and a quick-action button.
 */
export default function CriticalAlertsTable({ alerts }: CriticalAlertsTableProps) {
  const navigate = useNavigate();

  const handleViewAlert = () => {
    navigate(ROUTES.ALERTS);
  };

  return (
    <Card>
      <CardHeader
        title="Cảnh báo Nghiêm trọng"
        subtitle="Các vật tư cần xử lý ngay"
        action={
          <Button
            variant="ghost"
            size="sm"
            onClick={handleViewAlert}
            rightIcon={<ArrowRight size={14} />}
          >
            Xem tất cả
          </Button>
        }
      />

      {alerts.length > 0 ? (
        <div className="overflow-x-auto -mx-6">
          <table className="w-full">
            <thead>
              <tr className="border-b border-neutral-100">
                <th className="px-6 py-3 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Tên vật tư
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Mức độ
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Ngày thiếu hụt
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Tồn kho hiện tại
                </th>
                <th className="px-6 py-3 text-right text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                  Hành động
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {alerts.map((alert) => (
                <tr
                  key={alert.id}
                  className="hover:bg-neutral-50 transition-colors"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <AlertTriangle
                        size={14}
                        className={
                          alert.severity === 'critical'
                            ? 'text-danger-500'
                            : alert.severity === 'high'
                            ? 'text-warning-500'
                            : 'text-yellow-500'
                        }
                      />
                      <span className="text-sm font-medium text-neutral-900">
                        {alert.supply_name}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <AlertSeverityBadge severity={alert.severity} />
                  </td>
                  <td className="px-6 py-4 text-sm text-neutral-600">
                    {alert.shortage_date
                      ? formatDate(alert.shortage_date)
                      : '—'}
                  </td>
                  <td className="px-6 py-4 text-sm text-neutral-600">
                    {alert.current_stock !== null
                      ? `${alert.current_stock.toLocaleString('vi-VN')} đơn vị`
                      : '—'}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={handleViewAlert}
                    >
                      Chi tiết
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-neutral-400">
          <AlertTriangle size={32} className="mb-2 text-neutral-300" />
          <p className="text-sm">Không có cảnh báo nghiêm trọng</p>
        </div>
      )}
    </Card>
  );
}
