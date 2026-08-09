import { ChevronDown, Filter, Search, Boxes, Activity } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface AlertsFilters {
  search: string;
  status: string;     // 'all' | 'critical' | 'warning' | 'safe' | 'overstock'
  category: string;   // 'all' | category key
  disease: string;    // 'all' | disease_type key
}

interface Option {
  key: string;
  label: string;
}

interface Props {
  filters: AlertsFilters;
  onChange: (next: AlertsFilters) => void;
  categories: Option[];
  diseases: Option[];
}

const STATUS_OPTIONS: Option[] = [
  { key: 'all', label: 'Tất cả trạng thái' },
  { key: 'critical', label: 'Nguy hiểm' },
  { key: 'warning', label: 'Cảnh báo' },
  { key: 'safe', label: 'An toàn' },
  { key: 'overstock', label: 'Dư tồn' },
];

export default function AlertsToolbar({ filters, onChange, categories, diseases }: Props) {
  const update = (patch: Partial<AlertsFilters>) =>
    onChange({ ...filters, ...patch });

  return (
    <div className="px-5 py-4 border-b border-neutral-100 space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <SelectChip
          icon={<Filter className="w-3.5 h-3.5" />}
          value={filters.status}
          onChange={(v) => update({ status: v })}
          options={STATUS_OPTIONS}
        />
        <SelectChip
          icon={<Boxes className="w-3.5 h-3.5" />}
          value={filters.category}
          onChange={(v) => update({ category: v })}
          options={[{ key: 'all', label: 'Tất cả nhóm vật tư' }, ...categories]}
        />
        <SelectChip
          icon={<Activity className="w-3.5 h-3.5" />}
          value={filters.disease}
          onChange={(v) => update({ disease: v })}
          options={[{ key: 'all', label: 'Tất cả loại bệnh' }, ...diseases]}
        />
      </div>

      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
        <input
          type="text"
          value={filters.search}
          onChange={(e) => update({ search: e.target.value })}
          placeholder="Tìm nhanh trong danh sách..."
          className="w-full h-10 pl-9 pr-3 rounded-lg border border-neutral-200 bg-neutral-50 text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
        />
      </div>
    </div>
  );
}

function SelectChip({
  icon,
  value,
  onChange,
  options,
}: {
  icon: React.ReactNode;
  value: string;
  onChange: (v: string) => void;
  options: Option[];
}) {
  return (
    <div
      className={cn(
        'relative inline-flex items-center gap-2 h-9 pl-3 pr-8 rounded-lg border border-neutral-200',
        'bg-white hover:bg-neutral-50 text-sm font-medium text-neutral-700',
      )}
    >
      <span className="text-neutral-500">{icon}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none bg-transparent pr-1 focus:outline-none cursor-pointer"
      >
        {options.map((o) => (
          <option key={o.key} value={o.key}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
    </div>
  );
}
