import { ChevronDown, Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';
import { VN_PROVINCES } from '../../utils/vietnamRegions';

export interface ForecastFilters {
  disease: string;
  province: string; // 'all' = toàn thành phố, hoặc tên tỉnh/thành
  month: string;    // YYYY-MM
}

interface DiseaseOption {
  key: string;
  label: string;
}

interface Props {
  filters: ForecastFilters;
  onChange: (filters: ForecastFilters) => void;
  onAnalyze: () => void;
  diseases: DiseaseOption[];
  /** Map cascade từ DB (tỉnh → list quận có data thật) — gộp với master data VN. */
  regionDistricts?: Record<string, string[]>;
  isLoading?: boolean;
  disabled?: boolean;
}

export default function ForecastFilterBar({
  filters,
  onChange,
  onAnalyze,
  diseases,
  regionDistricts = {},
  isLoading = false,
  disabled = false,
}: Props) {
  const update = (patch: Partial<ForecastFilters>) =>
    onChange({ ...filters, ...patch });

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
        <FilterField label="Bệnh dịch">
          <SelectInput
            value={filters.disease}
            onChange={(v) => update({ disease: v })}
          >
            {diseases.length === 0 ? (
              <option value="">— Chưa có dữ liệu —</option>
            ) : (
              diseases.map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))
            )}
          </SelectInput>
        </FilterField>

        <FilterField label="Tỉnh/Thành phố">
          <SelectInput
            value={filters.province}
            onChange={(v) => update({ province: v })}
          >
            <option value="all">Toàn thành phố / cả nước</option>
            {VN_PROVINCES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </SelectInput>
        </FilterField>

        <FilterField label="Tháng dự báo">
          <input
            type="month"
            value={filters.month}
            onChange={(e) => update({ month: e.target.value })}
            className="w-full h-10 px-3 rounded-lg border border-neutral-300 bg-white text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
          />
        </FilterField>

        <button
          type="button"
          onClick={onAnalyze}
          disabled={disabled || isLoading}
          className={cn(
            'h-10 inline-flex items-center justify-center gap-2 px-5 rounded-lg text-sm font-semibold text-white transition',
            'bg-blue-600 hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed shadow-sm',
          )}
        >
          {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
          Phân tích
        </button>
      </div>
    </div>
  );
}

function FilterField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-neutral-500 mb-1.5">
        {label}
      </span>
      {children}
    </label>
  );
}

function SelectInput({
  value,
  onChange,
  children,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(
          'appearance-none w-full h-10 pl-3 pr-9 rounded-lg border border-neutral-300 bg-white',
          'text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500',
          'disabled:bg-neutral-50 disabled:text-neutral-400 disabled:cursor-not-allowed',
        )}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
    </div>
  );
}
