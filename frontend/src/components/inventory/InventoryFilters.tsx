import { Filter } from 'lucide-react';

interface InventoryFiltersProps {
  selectedCategory: string;
  selectedRiskLevel: string;
  onCategoryChange: (category: string) => void;
  onRiskLevelChange: (riskLevel: string) => void;
}

const categories: Array<{ value: string; label: string }> = [
  { value: 'all', label: 'Tất cả' },
  { value: 'mask', label: 'Khẩu trang' },
  { value: 'glove', label: 'Găng tay' },
  { value: 'test_kit', label: 'Kit xét nghiệm' },
  { value: 'disinfectant', label: 'Dung dịch sát khuẩn' },
  { value: 'medicine', label: 'Thuốc' },
  { value: 'iv_fluid', label: 'Dịch truyền' },
  { value: 'other', label: 'Khác' },
];

const riskLevels: Array<{ value: string; label: string }> = [
  { value: 'all', label: 'Tất cả' },
  { value: 'critical', label: 'Nguy cơ' },
  { value: 'low', label: 'Sắp hết' },
  { value: 'safe', label: 'An toàn' },
];

export default function InventoryFilters({
  selectedCategory,
  selectedRiskLevel,
  onCategoryChange,
  onRiskLevelChange,
}: InventoryFiltersProps) {
  return (
    <div className="flex items-center gap-4 p-4 bg-white border border-neutral-200 rounded-lg">
      <div className="flex items-center gap-2 text-neutral-600">
        <Filter className="w-4 h-4" />
        <span className="text-sm font-medium">Lọc:</span>
      </div>

      {/* Category Filter */}
      <div className="flex items-center gap-2">
        <label htmlFor="category-filter" className="text-sm text-neutral-600">
          Danh mục:
        </label>
        <select
          id="category-filter"
          value={selectedCategory}
          onChange={(e) => onCategoryChange(e.target.value)}
          className="px-3 py-1.5 text-sm border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          {categories.map((cat) => (
            <option key={cat.value} value={cat.value}>
              {cat.label}
            </option>
          ))}
        </select>
      </div>

      {/* Risk Level Filter */}
      <div className="flex items-center gap-2">
        <label htmlFor="risk-filter" className="text-sm text-neutral-600">
          Mức độ rủi ro:
        </label>
        <select
          id="risk-filter"
          value={selectedRiskLevel}
          onChange={(e) => onRiskLevelChange(e.target.value)}
          className="px-3 py-1.5 text-sm border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          {riskLevels.map((level) => (
            <option key={level.value} value={level.value}>
              {level.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
