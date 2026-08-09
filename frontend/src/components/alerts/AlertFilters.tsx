import { Filter, Calendar } from 'lucide-react';
import Button from '../common/Button';
import type { AlertSeverity } from '../../types/alerts';
import { ALERT_SEVERITY_LABELS } from '../../types/alerts';

interface AlertFiltersProps {
  selectedSeverity: AlertSeverity | 'all';
  selectedDateRange: string;
  showResolved: boolean;
  onSeverityChange: (severity: AlertSeverity | 'all') => void;
  onDateRangeChange: (range: string) => void;
  onShowResolvedChange: (show: boolean) => void;
}

const DATE_RANGES = [
  { value: '7', label: '7 ngày' },
  { value: '30', label: '30 ngày' },
  { value: '90', label: '90 ngày' },
  { value: 'all', label: 'Tất cả' },
];

const SEVERITY_OPTIONS: Array<{ value: AlertSeverity | 'all'; label: string }> = [
  { value: 'all', label: 'Tất cả mức độ' },
  ...Object.entries(ALERT_SEVERITY_LABELS).map(([value, label]) => ({
    value: value as AlertSeverity,
    label,
  })),
];

export default function AlertFilters({
  selectedSeverity,
  selectedDateRange,
  showResolved,
  onSeverityChange,
  onDateRangeChange,
  onShowResolvedChange,
}: AlertFiltersProps) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4">
      <div className="flex flex-col sm:flex-row gap-4 flex-wrap">
        {/* Severity Filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-neutral-500 shrink-0" />
          <label htmlFor="severity-filter" className="text-sm font-medium text-neutral-600 shrink-0">
            Mức độ:
          </label>
          <select
            id="severity-filter"
            value={selectedSeverity}
            onChange={(e) => onSeverityChange(e.target.value as AlertSeverity | 'all')}
            className="px-3 py-1.5 text-sm border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            {SEVERITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Date Range Filter */}
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-neutral-500 shrink-0" />
          <span className="text-sm font-medium text-neutral-600 shrink-0">Thời gian:</span>
          <div className="flex gap-1.5">
            {DATE_RANGES.map((range) => (
              <Button
                key={range.value}
                variant={selectedDateRange === range.value ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => onDateRangeChange(range.value)}
              >
                {range.label}
              </Button>
            ))}
          </div>
        </div>

        {/* Show Resolved Toggle */}
        <div className="flex items-center gap-2 sm:ml-auto">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <div
              onClick={() => onShowResolvedChange(!showResolved)}
              className={`relative inline-flex items-center w-10 h-5 rounded-full transition-colors duration-200 cursor-pointer ${
                showResolved ? 'bg-primary-600' : 'bg-neutral-300'
              }`}
            >
              <span
                className={`absolute w-4 h-4 bg-white rounded-full shadow transition-transform duration-200 ${
                  showResolved ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </div>
            <span className="text-sm text-neutral-600">Hiển thị đã xử lý</span>
          </label>
        </div>
      </div>
    </div>
  );
}
