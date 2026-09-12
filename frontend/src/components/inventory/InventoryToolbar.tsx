import { ChevronDown, Search } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface InventoryFilters {
  search: string;
  category: string; // 'all' | category key
  status: string;   // 'all' | 'normal' | 'low' | 'critical'
}

interface CategoryOption {
  key: string;
  label: string;
}

interface Props {
  filters: InventoryFilters;
  onChange: (next: InventoryFilters) => void;
  categories: CategoryOption[];
}

const STATUS_OPTIONS: CategoryOption[] = [
  { key: 'all', label: 'Tất cả' },
  { key: 'normal', label: 'Bình thường' },
  { key: 'low', label: 'Dưới ngưỡng' },
  { key: 'critical', label: 'Nguy cấp' },
];

export default function InventoryToolbar({ filters, onChange, categories }: Props) {
  const update = (patch: Partial<InventoryFilters>) =>
    onChange({ ...filters, ...patch });

  return (
    <div className="space-y-3 px-5 py-4 border-b border-neutral-100">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
          <input
            type="text"
            value={filters.search}
            onChange={(e) => update({ search: e.target.value })}
            placeholder="Tìm kiếm theo tên, mã vật tư..."
            className="w-full h-10 pl-9 pr-3 rounded-lg border border-neutral-200 bg-neutral-50 text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <SelectInline
            label="Loại:"
            value={filters.category}
            onChange={(v) => update({ category: v })}
            options={[{ key: 'all', label: 'Tất cả' }, ...categories]}
          />
          <SelectInline
            label="Trạng thái:"
            value={filters.status}
            onChange={(v) => update({ status: v })}
            options={STATUS_OPTIONS}
          />
        </div>
      </div>
    </div>
  );
}

function SelectInline({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: CategoryOption[];
}) {
  return (
    <label className="inline-flex items-center gap-2 text-sm text-neutral-600">
      {label}
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            'appearance-none h-10 pl-3 pr-8 rounded-lg border border-neutral-200 bg-white',
            'text-sm font-medium text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500',
          )}
        >
          {options.map((o) => (
            <option key={o.key} value={o.key}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
      </div>
    </label>
  );
}
