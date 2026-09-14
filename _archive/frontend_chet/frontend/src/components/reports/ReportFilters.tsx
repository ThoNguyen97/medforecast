import { Filter, Calendar } from 'lucide-react';
import type { ReportFilters } from '../../types/reports';
import { SUPPLY_CATEGORY_LABELS, DISEASE_TYPE_LABELS } from '../../utils/constants';

interface ReportFiltersProps {
  filters: ReportFilters;
  reportType: 'consumption' | 'forecast-accuracy' | 'inventory-turnover';
  onChange: (filters: ReportFilters) => void;
}

/**
 * Filter controls for the Reports page.
 * Shows different fields depending on the active report type.
 */
export default function ReportFiltersComponent({
  filters,
  reportType,
  onChange,
}: ReportFiltersProps) {
  const handleChange = (key: keyof ReportFilters, value: string) => {
    onChange({ ...filters, [key]: value || undefined });
  };

  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Filter size={15} className="text-neutral-400" />
        <span className="text-sm font-medium text-neutral-700">Bộ lọc báo cáo</span>
      </div>

      <div className="flex flex-wrap gap-3">
        {/* Date range — available for all report types */}
        <div className="flex items-center gap-2">
          <Calendar size={14} className="text-neutral-400 shrink-0" />
          <label className="text-xs text-neutral-500 whitespace-nowrap">Từ ngày</label>
          <input
            type="date"
            value={filters.start_date ?? ''}
            onChange={(e) => handleChange('start_date', e.target.value)}
            className="border border-neutral-300 rounded-lg px-2.5 py-1.5 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-neutral-500 whitespace-nowrap">Đến ngày</label>
          <input
            type="date"
            value={filters.end_date ?? ''}
            onChange={(e) => handleChange('end_date', e.target.value)}
            className="border border-neutral-300 rounded-lg px-2.5 py-1.5 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />
        </div>

        {/* Category filter — consumption & turnover */}
        {(reportType === 'consumption' || reportType === 'inventory-turnover') && (
          <div className="flex items-center gap-2">
            <label className="text-xs text-neutral-500 whitespace-nowrap">Danh mục</label>
            <select
              value={filters.category ?? ''}
              onChange={(e) => handleChange('category', e.target.value)}
              className="border border-neutral-300 rounded-lg px-2.5 py-1.5 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="">Tất cả</option>
              {Object.entries(SUPPLY_CATEGORY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Disease type filter — forecast-accuracy */}
        {reportType === 'forecast-accuracy' && (
          <div className="flex items-center gap-2">
            <label className="text-xs text-neutral-500 whitespace-nowrap">Loại bệnh</label>
            <select
              value={filters.disease_type ?? ''}
              onChange={(e) => handleChange('disease_type', e.target.value)}
              className="border border-neutral-300 rounded-lg px-2.5 py-1.5 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="">Tất cả</option>
              {Object.entries(DISEASE_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Model filter — forecast-accuracy only */}
        {reportType === 'forecast-accuracy' && (
          <div className="flex items-center gap-2">
            <label className="text-xs text-neutral-500 whitespace-nowrap">Mô hình</label>
            <select
              value={filters.model_used ?? ''}
              onChange={(e) => handleChange('model_used', e.target.value)}
              className="border border-neutral-300 rounded-lg px-2.5 py-1.5 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="">Tất cả</option>
              <option value="xgboost">XGBoost</option>
              <option value="lstm">LSTM</option>
              <option value="prophet">Prophet</option>
              <option value="ensemble">Ensemble</option>
            </select>
          </div>
        )}
      </div>
    </div>
  );
}
