import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { useMemo, useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import Card, { CardHeader } from '../common/Card';
import LoadingSpinner from '../common/LoadingSpinner';
import type { ConsumptionReport as ConsumptionReportType } from '../../types/reports';
import { SUPPLY_CATEGORY_LABELS } from '../../utils/constants';
import { formatNumber } from '../../utils/formatters';

// Colour palette for bar chart segments
const CATEGORY_COLORS = [
  '#3b82f6',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#06b6d4',
  '#f97316',
];

interface ConsumptionReportProps {
  data: ConsumptionReportType | undefined;
  isLoading: boolean;
}

/**
 * Displays a bar chart and summary for the consumption report.
 */
export default function ConsumptionReport({ data, isLoading }: ConsumptionReportProps) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Flatten supplies for pagination, keep category info per row
  const allRows = useMemo(() => {
    if (!data) return [] as Array<{
      category: string;
      categoryColor: string;
      supply_name: string;
      unit: string;
      total_required: number;
      avg_daily_consumption: number;
      active_days: number;
    }>;
    const list: Array<any> = [];
    data.categories.forEach((cat, ci) => {
      const color = CATEGORY_COLORS[ci % CATEGORY_COLORS.length];
      cat.supplies.forEach((supply) => {
        list.push({
          category: cat.category,
          categoryColor: color,
          supply_name: supply.supply_name,
          unit: supply.unit,
          total_required: supply.total_required,
          avg_daily_consumption: supply.avg_daily_consumption,
          active_days: supply.active_days,
        });
      });
    });
    return list;
  }, [data]);

  // Reset trang khi data hoặc pageSize đổi
  useEffect(() => {
    setPage(1);
  }, [data, pageSize]);

  const totalPages = Math.max(1, Math.ceil(allRows.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * pageSize;
  const pagedRows = allRows.slice(start, start + pageSize);

  if (isLoading) {
    return (
      <Card>
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" label="Đang tải báo cáo tiêu thụ..." />
        </div>
      </Card>
    );
  }

  if (!data || data.categories.length === 0) {
    return (
      <Card>
        <CardHeader
          title="Báo cáo Tiêu thụ Vật tư"
          subtitle="Lượng vật tư yêu cầu theo danh mục trong kỳ báo cáo"
        />
        <div className="flex items-center justify-center h-40 text-neutral-400 text-sm">
          Không có dữ liệu tiêu thụ trong khoảng thời gian đã chọn
        </div>
      </Card>
    );
  }

  // Prepare chart data — one bar per category
  const chartData = data.categories.map((cat, i) => ({
    name: SUPPLY_CATEGORY_LABELS[cat.category] ?? cat.category,
    rawCategory: cat.category,
    total_required: cat.total_required,
    color: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
  }));

  return (
    <Card>
      <CardHeader
        title="Báo cáo Tiêu thụ Vật tư"
        subtitle={`Kỳ: ${data.period.start_date} — ${data.period.end_date} · ${data.summary.categories_count} danh mục`}
        action={
          <span className="text-xs text-neutral-400">
            Tổng yêu cầu:{' '}
            <span className="font-semibold text-neutral-700">
              {formatNumber(data.summary.total_required_across_all_categories)}
            </span>
          </span>
        }
      />

      {/* Bar chart */}
      <div className="h-72 mb-6">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="name"
              stroke="#6b7280"
              style={{ fontSize: '11px' }}
              tick={{ fill: '#6b7280' }}
            />
            <YAxis
              stroke="#6b7280"
              style={{ fontSize: '11px' }}
              tick={{ fill: '#6b7280' }}
              tickFormatter={(v) => formatNumber(v)}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              formatter={(value: number) => [formatNumber(value), 'Tổng yêu cầu']}
            />
            <Legend wrapperStyle={{ fontSize: '12px' }} />
            <Bar dataKey="total_required" name="Tổng yêu cầu" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Category breakdown table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50">
              <th className="px-4 py-2.5 text-left font-semibold text-neutral-600">Danh mục</th>
              <th className="px-4 py-2.5 text-left font-semibold text-neutral-600">Vật tư</th>
              <th className="px-4 py-2.5 text-right font-semibold text-neutral-600">Tổng yêu cầu</th>
              <th className="px-4 py-2.5 text-right font-semibold text-neutral-600">TB/ngày</th>
              <th className="px-4 py-2.5 text-right font-semibold text-neutral-600">Số ngày</th>
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((row, idx) => (
              <tr
                key={`${start + idx}`}
                className="border-b border-neutral-100 hover:bg-neutral-50 transition-colors"
              >
                <td className="px-4 py-2.5 font-medium text-neutral-700 align-top border-r border-neutral-100">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: row.categoryColor }}
                    />
                    {SUPPLY_CATEGORY_LABELS[row.category] ?? row.category}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-neutral-700">{row.supply_name}</td>
                <td className="px-4 py-2.5 text-right text-neutral-700 font-medium">
                  {formatNumber(row.total_required)}{' '}
                  <span className="text-neutral-400 font-normal text-xs">{row.unit}</span>
                </td>
                <td className="px-4 py-2.5 text-right text-neutral-500">
                  {formatNumber(row.avg_daily_consumption, 1)}
                </td>
                <td className="px-4 py-2.5 text-right text-neutral-500">{row.active_days}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      {allRows.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 mt-4 text-sm">
          <div className="flex items-center gap-2 text-neutral-500">
            <span>Hiển thị</span>
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="border border-neutral-200 rounded px-2 py-1 text-sm"
            >
              {[5, 10, 20, 50].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
            <span>
              / {allRows.length} dòng · Trang {safePage}/{totalPages}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(1)}
              disabled={safePage <= 1}
              className="px-2 py-1 text-xs border rounded disabled:opacity-30"
            >
              «
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage <= 1}
              className="px-2 py-1 border rounded disabled:opacity-30 inline-flex items-center"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 py-1 text-neutral-600">{safePage}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage >= totalPages}
              className="px-2 py-1 border rounded disabled:opacity-30 inline-flex items-center"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage(totalPages)}
              disabled={safePage >= totalPages}
              className="px-2 py-1 text-xs border rounded disabled:opacity-30"
            >
              »
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
