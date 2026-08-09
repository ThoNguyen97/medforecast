import {
  Activity,
  TrendingUp,
  Boxes,
  ShoppingCart,
} from 'lucide-react';
import { cn } from '../../utils/cn';

export type ReportKind =
  | 'epidemic'
  | 'forecast'
  | 'inventory'
  | 'shortage'
  | 'procurement'
  | 'accuracy';

export interface ReportTypeMeta {
  key: ReportKind;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string; // tailwind color base, e.g., 'blue', 'rose'
}

export const REPORT_TYPES: ReportTypeMeta[] = [
  {
    key: 'epidemic',
    title: 'Tình hình dịch bệnh',
    description: 'Số ca theo tháng, theo bệnh và theo khu vực.',
    icon: Activity,
    accent: 'rose',
  },
  {
    key: 'forecast',
    title: 'Dự báo ca bệnh',
    description: 'Số ca dự báo, mức nguy cơ và lý do dự báo.',
    icon: TrendingUp,
    accent: 'blue',
  },
  {
    key: 'inventory',
    title: 'Tồn kho vật tư',
    description: 'Danh sách vật tư, ngưỡng an toàn và trạng thái.',
    icon: Boxes,
    accent: 'emerald',
  },
  {
    key: 'procurement',
    title: 'Đề xuất nhập kho',
    description: 'Danh sách vật tư cần nhập kèm lý do đề xuất.',
    icon: ShoppingCart,
    accent: 'violet',
  },
];

const ACCENT_MAP: Record<string, { bg: string; icon: string; ring: string }> = {
  blue: { bg: 'bg-blue-50', icon: 'text-blue-600', ring: 'ring-blue-500/40' },
  rose: { bg: 'bg-rose-50', icon: 'text-rose-600', ring: 'ring-rose-500/40' },
  emerald: { bg: 'bg-emerald-50', icon: 'text-emerald-600', ring: 'ring-emerald-500/40' },
  amber: { bg: 'bg-amber-50', icon: 'text-amber-600', ring: 'ring-amber-500/40' },
  violet: { bg: 'bg-violet-50', icon: 'text-violet-600', ring: 'ring-violet-500/40' },
  sky: { bg: 'bg-sky-50', icon: 'text-sky-600', ring: 'ring-sky-500/40' },
};

interface Props {
  active: ReportKind;
  onSelect: (kind: ReportKind) => void;
}

export default function ReportTypePicker({ active, onSelect }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {REPORT_TYPES.map((t) => {
        const Icon = t.icon;
        const accent = ACCENT_MAP[t.accent];
        const isActive = active === t.key;
        return (
          <button
            type="button"
            key={t.key}
            onClick={() => onSelect(t.key)}
            className={cn(
              'text-left rounded-2xl border bg-white p-4 transition',
              'hover:shadow-card-hover hover:-translate-y-0.5',
              isActive
                ? `border-transparent ring-2 ${accent.ring} shadow-sm`
                : 'border-neutral-200',
            )}
          >
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  'shrink-0 w-10 h-10 rounded-xl flex items-center justify-center',
                  accent.bg,
                )}
              >
                <Icon className={cn('w-5 h-5', accent.icon)} />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-neutral-900 leading-snug">
                  {t.title}
                </p>
                <p className="text-xs text-neutral-500 mt-1 leading-relaxed">
                  {t.description}
                </p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
