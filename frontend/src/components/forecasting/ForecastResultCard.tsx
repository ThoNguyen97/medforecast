import { AlertTriangle } from 'lucide-react';
import { cn } from '../../utils/cn';

type RiskLevel = 'low' | 'medium' | 'high' | 'very_high';

interface Props {
  predictedCases: number;
  diseaseLabel: string;
  region: string;
  targetMonth: number;
  targetYear: number;
  riskLevel: RiskLevel;
  riskLabel: string;
  /** Độ chính xác mô hình (%) = 100 − MAPE. Bỏ qua nếu không có. */
  accuracyPct?: number | null;
}

const riskConfig: Record<RiskLevel, { badge: string; pill: string; ring: string }> = {
  low: {
    badge: 'bg-emerald-500',
    pill: 'bg-emerald-50 border-emerald-100 text-emerald-700',
    ring: 'border-emerald-100 bg-emerald-50/50',
  },
  medium: {
    badge: 'bg-amber-500',
    pill: 'bg-amber-50 border-amber-100 text-amber-700',
    ring: 'border-amber-100 bg-amber-50/40',
  },
  high: {
    badge: 'bg-red-500',
    pill: 'bg-red-50 border-red-100 text-red-700',
    ring: 'border-red-100 bg-red-50/50',
  },
  very_high: {
    badge: 'bg-red-600',
    pill: 'bg-red-50 border-red-200 text-red-700',
    ring: 'border-red-200 bg-red-50/60',
  },
};

export default function ForecastResultCard({
  predictedCases,
  diseaseLabel,
  region,
  targetMonth,
  targetYear,
  riskLevel,
  riskLabel,
  accuracyPct,
}: Props) {
  const cfg = riskConfig[riskLevel];

  // Màu cho độ chính xác: cao→xanh, vừa→hổ phách, thấp→đỏ
  const accColor =
    accuracyPct == null
      ? ''
      : accuracyPct >= 80
      ? 'text-emerald-600'
      : accuracyPct >= 60
      ? 'text-amber-600'
      : 'text-red-600';

  return (
    <div
      className={cn(
        'relative rounded-2xl border p-5 overflow-hidden',
        cfg.ring,
      )}
    >
      {/* Faded warning watermark */}
      <AlertTriangle className="absolute right-4 top-1/2 -translate-y-1/2 w-24 h-24 text-red-200/40 pointer-events-none" />

      <div className="relative flex items-center gap-2 text-red-600 text-xs font-semibold uppercase tracking-wide">
        Dự báo (tháng {String(targetMonth).padStart(2, '0')}/{targetYear})
      </div>

      <div className="relative mt-3 text-4xl font-extrabold text-neutral-900 tabular-nums">
        {predictedCases.toLocaleString('vi-VN')} <span className="text-2xl font-bold">ca</span>
      </div>

      <p className="relative mt-1.5 text-sm text-neutral-500">
        {diseaseLabel} - {region}
      </p>

      <div
        className={cn(
          'relative mt-5 flex items-center justify-between rounded-xl border px-3.5 py-2.5',
          cfg.pill,
        )}
      >
        <span className="text-xs font-semibold uppercase tracking-wide">
          Mức nguy cơ
        </span>
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold text-white',
            cfg.badge,
          )}
        >
          {riskLabel.toUpperCase()}
        </span>
      </div>

      {accuracyPct != null && (
        <div className="relative mt-2.5 flex items-center justify-between rounded-xl border border-neutral-200 bg-white/70 px-3.5 py-2.5">
          <span className="text-xs font-semibold uppercase tracking-wide text-neutral-600">
            Độ chính xác mô hình
          </span>
          <span className={cn('text-sm font-extrabold tabular-nums', accColor)}>
            {accuracyPct.toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
}
