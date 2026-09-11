import { Calendar } from 'lucide-react';
import Card from '../common/Card';
import Button from '../common/Button';
import type { DiseaseType } from '../../types/epidemiology';
import { DISEASE_TYPE_LABELS } from '../../types/epidemiology';

interface EpidemiologyFiltersProps {
  selectedDiseaseType: DiseaseType | 'all';
  selectedDateRange: string;
  onDiseaseTypeChange: (diseaseType: DiseaseType | 'all') => void;
  onDateRangeChange: (range: string) => void;
}

const DATE_RANGES = [
  { value: '7', label: '7 ngày' },
  { value: '30', label: '30 ngày' },
  { value: '90', label: '90 ngày' },
  { value: 'all', label: 'Tất cả' },
];

export default function EpidemiologyFilters({
  selectedDiseaseType,
  selectedDateRange,
  onDiseaseTypeChange,
  onDateRangeChange,
}: EpidemiologyFiltersProps) {
  return (
    <Card>
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Disease Type Filter */}
        <div className="flex-1">
          <label className="block text-sm font-medium text-neutral-700 mb-2">
            Loại dịch bệnh
          </label>
          <select
            value={selectedDiseaseType}
            onChange={(e) => onDiseaseTypeChange(e.target.value as DiseaseType | 'all')}
            className="w-full px-3 py-2 border border-neutral-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="all">Tất cả loại dịch bệnh</option>
            {Object.entries(DISEASE_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* Date Range Filter */}
        <div className="flex-1">
          <label className="block text-sm font-medium text-neutral-700 mb-2">
            <Calendar className="inline w-4 h-4 mr-1" />
            Khoảng thời gian
          </label>
          <div className="flex gap-2">
            {DATE_RANGES.map((range) => (
              <Button
                key={range.value}
                variant={selectedDateRange === range.value ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => onDateRangeChange(range.value)}
                className="flex-1"
              >
                {range.label}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
