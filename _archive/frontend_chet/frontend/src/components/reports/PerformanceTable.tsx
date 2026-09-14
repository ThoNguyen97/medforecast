import { useMemo } from 'react';
import { TrendingUp } from 'lucide-react';
import Card, { CardHeader } from '../common/Card';
import Badge from '../common/Badge';
import LoadingSpinner from '../common/LoadingSpinner';
import type { ForecastAccuracyReport, MonthlyPerformanceRow } from '../../types/reports';
import { DISEASE_TYPE_LABELS } from '../../utils/constants';

interface PerformanceTableProps {
  data: ForecastAccuracyReport | undefined;
  isLoading: boolean;
}

/**
 * Monthly summary performance table derived from forecast accuracy data.
 */
export default function PerformanceTable({ data, isLoading }: PerformanceTableProps) {
  // Aggregate time_series into monthly rows
  const monthlyRows = useMemo<MonthlyPerformanceRow[]>(() => {
    if (!data || data.time_series.length === 0) return [];

    const buckets: Record<
      string,
      {
        month: string;
        total: number;
        mae_sum: number;
        mae_count: number;
        rmse_sum: number;
        rmse_count: number;
        mape_sum: number;
        mape_count: number;
        model_counts: Record<string, number>;
      }
    > = {};

    for (const point of data.time_series) {
      const date = new Date(point.date);
      const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;

      if (!buckets[month]) {
        buckets[month] = {
          month,
          total: 0,
          mae_sum: 0,
          mae_count: 0,
          rmse_sum: 0,
          rmse_count: 0,
          mape_sum: 0,
          mape_count: 0,
          model_counts: {},
        };
      }

      const b = buckets[month];
      b.total += 1;
      if (point.mae !== null) { b.mae_sum += point.mae; b.mae_count += 1; }
      if (point.rmse !== null) { b.rmse_sum += point.rmse; b.rmse_count += 1; }
      if (point.mape !== null) { b.mape_sum += point.mape; b.mape_count += 1; }
      b.model_counts[point.model] = (b.model_counts[point.model] ?? 0) + 1;
    }

    return Object.values(buckets)
      .sort((a, b) => a.month.localeCompare(b.month))
      .map((b) => {
        const [year, month] = b.month.split('-');
        const bestModel = Object.entries(b.model_counts).sort((x, y) => y[1] - x[1])[0]?.[0] ?? null;
        return {
          month: b.month,
          month_label: `Tháng ${parseInt(month)}/${year}`,
          total_forecasts: b.total,
          avg_mae: b.mae_count > 0 ? parseFloat((b.mae_sum / b.mae_count).toFixed(2)) : null,
          avg_rmse: b.rmse_count > 0 ? parseFloat((b.rmse_sum / b.rmse_count).toFixed(2)) : null,
          avg_mape: b.mape_count > 0 ? parseFloat((b.mape_sum / b.mape_count).toFixed(2)) : null,
          best_model: bestModel,
        };
      });
  }, [data]);

  if (isLoading) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <LoadingSpinner size="lg" label="Đang tải bảng hiệu suất..." />
        </div>
      </Card>
    );
  }

  const hasData = data && data.time_series.length > 0;

  return (
    <Card>
      <CardHeader
        title="Hiệu suất Dự báo Theo Tháng"
        subtitle={
          data
            ? `Kỳ: ${data.period.start_date} — ${data.period.end_date} · ${data.summary.total_forecasts} bản ghi`
            : 'Tổng hợp độ chính xác mô hình theo tháng'
        }
        action={
          data?.summary.best_model_by_mape ? (
            <div className="flex items-center gap-1.5 text-xs text-neutral-500">
              <TrendingUp size={13} className="text-success-500" />
              Tốt nhất:{' '}
              <span className="font-semibold text-neutral-700">
                {data.summary.best_model_by_mape}
              </span>
            </div>
          ) : undefined
        }
      />

      {/* Model summary cards */}
      {data && data.model_performance.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          {data.model_performance.map((model) => (
            <div
              key={model.model}
              className="bg-neutral-50 rounded-lg border border-neutral-200 p-3"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-semibold text-neutral-700 uppercase">
                  {model.model}
                </span>
                {model.model === data.summary.best_model_by_mape && (
                  <Badge variant="success" size="sm">Tốt nhất</Badge>
                )}
              </div>
              <div className="space-y-0.5">
                <p className="text-xs text-neutral-500">
                  MAE: <span className="font-medium text-neutral-700">{model.avg_mae ?? '—'}</span>
                </p>
                <p className="text-xs text-neutral-500">
                  RMSE: <span className="font-medium text-neutral-700">{model.avg_rmse ?? '—'}</span>
                </p>
                <p className="text-xs text-neutral-500">
                  MAPE: <span className="font-medium text-neutral-700">{model.avg_mape !== null ? `${model.avg_mape}%` : '—'}</span>
                </p>
                <p className="text-xs text-neutral-400">{model.sample_count} mẫu</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Monthly breakdown table */}
      {!hasData ? (
        <div className="flex items-center justify-center h-32 text-neutral-400 text-sm">
          Không có dữ liệu trong khoảng thời gian đã chọn
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-2.5 text-left font-semibold text-neutral-600">Tháng</th>
                <th className="px-4 py-2.5 text-right font-semibold text-neutral-600">Số dự báo</th>
                <th className="px-4 py-2.5 text-right font-semibold text-neutral-600">MAE TB</th>
                <th className="px-4 py-2.5 text-right font-semibold text-neutral-600">RMSE TB</th>
                <th className="px-4 py-2.5 text-right font-semibold text-neutral-600">MAPE TB</th>
                <th className="px-4 py-2.5 text-left font-semibold text-neutral-600">Mô hình chính</th>
              </tr>
            </thead>
            <tbody>
              {monthlyRows.map((row) => (
                <tr
                  key={row.month}
                  className="border-b border-neutral-100 hover:bg-neutral-50 transition-colors"
                >
                  <td className="px-4 py-2.5 font-medium text-neutral-700">{row.month_label}</td>
                  <td className="px-4 py-2.5 text-right text-neutral-700">{row.total_forecasts}</td>
                  <td className="px-4 py-2.5 text-right text-neutral-500">
                    {row.avg_mae !== null ? row.avg_mae.toFixed(2) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right text-neutral-500">
                    {row.avg_rmse !== null ? row.avg_rmse.toFixed(2) : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {row.avg_mape !== null ? (
                      <span
                        className={
                          row.avg_mape < 10
                            ? 'text-success-600 font-medium'
                            : row.avg_mape < 20
                            ? 'text-warning-600 font-medium'
                            : 'text-danger-600 font-medium'
                        }
                      >
                        {row.avg_mape.toFixed(2)}%
                      </span>
                    ) : (
                      <span className="text-neutral-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {row.best_model ? (
                      <Badge variant="info" size="sm">{row.best_model}</Badge>
                    ) : (
                      <span className="text-neutral-400 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Active filters info */}
      {data?.filters && (data.filters.disease_type || data.filters.model_used) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {data.filters.disease_type && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 text-xs border border-primary-200">
              Bệnh: {DISEASE_TYPE_LABELS[data.filters.disease_type] ?? data.filters.disease_type}
            </span>
          )}
          {data.filters.model_used && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 text-xs border border-primary-200">
              Mô hình: {data.filters.model_used}
            </span>
          )}
        </div>
      )}
    </Card>
  );
}
