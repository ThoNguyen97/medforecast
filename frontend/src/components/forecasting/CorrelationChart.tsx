import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface CorrelationItem {
  year: number;
  cases: number;
  temp: number | null;
  humidity: number | null;
  rainfall: number | null;
  aqi: number | null;
  pm25: number | null;
  is_forecast: boolean;
}

interface Props {
  data: CorrelationItem[];
  targetMonth: number;
  coefficients?: {
    temp: number | null;
    humidity: number | null;
    rainfall: number | null;
    aqi: number | null;
    pm25: number | null;
  };
}

const SERIES_META: Array<{
  key: keyof CorrelationItem;
  label: string;
  color: string;
  dashed?: boolean;
}> = [
  { key: 'temp', label: 'Nhiệt độ', color: '#0f766e' },
  { key: 'humidity', label: 'Độ ẩm', color: '#92400e' },
  { key: 'rainfall', label: 'Lượng mưa', color: '#3b82f6', dashed: true },
  { key: 'aqi', label: 'AQI', color: '#dc2626' },
  { key: 'pm25', label: 'PM2.5', color: '#334155' },
];

export default function CorrelationChart({ data, targetMonth, coefficients }: Props) {
  const formatted = data.map((d) => ({
    label: String(d.year),
    'Số ca mắc': d.cases,
    'Nhiệt độ': d.temp,
    'Độ ẩm': d.humidity,
    'Lượng mưa': d.rainfall,
    AQI: d.aqi,
    'PM2.5': d.pm25,
    is_forecast: d.is_forecast,
  }));

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold text-neutral-900 max-w-[260px]">
          Tương quan Thời tiết & Dịch bệnh (Tháng {targetMonth} qua các năm)
        </h3>
        <Legend />
      </div>

      {coefficients && <CoefficientsBar coefficients={coefficients} />}

      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={formatted} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            {/* Trái: số ca mắc (0-600) */}
            <YAxis
              yAxisId="left"
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            {/* Phải: thời tiết (0-100) */}
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: 8,
                fontSize: 12,
              }}
            />

            {/* Cột số ca mắc */}
            <Bar
              yAxisId="left"
              dataKey="Số ca mắc"
              barSize={42}
              radius={[6, 6, 0, 0]}
            >
              {formatted.map((d, idx) => (
                <Cell key={idx} fill={d.is_forecast ? '#2563eb' : '#bfdbfe'} />
              ))}
            </Bar>

            {/* Đường thời tiết */}
            {SERIES_META.map((s) => (
              <Line
                key={s.label}
                yAxisId="right"
                type="monotone"
                dataKey={s.label}
                stroke={s.color}
                strokeWidth={3}
                strokeDasharray={s.dashed ? '6 4' : '0'}
                dot={false}
                connectNulls
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function CoefficientsBar({
  coefficients,
}: {
  coefficients: {
    temp: number | null;
    humidity: number | null;
    rainfall: number | null;
    aqi: number | null;
    pm25: number | null;
  };
}) {
  const items: { key: keyof typeof coefficients; label: string; color: string }[] = [
    { key: 'temp', label: 'Nhiệt độ', color: '#0f766e' },
    { key: 'humidity', label: 'Độ ẩm', color: '#92400e' },
    { key: 'rainfall', label: 'Lượng mưa', color: '#3b82f6' },
    { key: 'aqi', label: 'AQI', color: '#dc2626' },
    { key: 'pm25', label: 'PM2.5', color: '#334155' },
  ];

  const interpret = (r: number | null): string => {
    if (r === null) return '—';
    const abs = Math.abs(r);
    if (abs < 0.2) return 'Rất yếu';
    if (abs < 0.4) return 'Yếu';
    if (abs < 0.6) return 'Trung bình';
    if (abs < 0.8) return 'Mạnh';
    return 'Rất mạnh';
  };

  const tone = (r: number | null): string => {
    if (r === null) return 'text-neutral-400';
    const abs = Math.abs(r);
    if (abs >= 0.6) return r > 0 ? 'text-emerald-600' : 'text-red-600';
    if (abs >= 0.3) return r > 0 ? 'text-emerald-500' : 'text-amber-600';
    return 'text-neutral-500';
  };

  return (
    <div className="mb-4 rounded-xl bg-neutral-50 border border-neutral-100 p-3">
      <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wide mb-2">
        Hệ số tương quan Pearson với số ca mắc
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        {items.map((it) => {
          const r = coefficients[it.key];
          return (
            <div key={it.key} className="flex items-center gap-2 min-w-0">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: it.color }}
              />
              <div className="min-w-0">
                <p className="text-[11px] text-neutral-500 truncate">{it.label}</p>
                <p className={`text-sm font-semibold tabular-nums ${tone(r)}`}>
                  {r !== null ? (r > 0 ? '+' : '') + r.toFixed(2) : '—'}
                  <span className="ml-1 text-[10px] font-normal text-neutral-400">
                    {interpret(r)}
                  </span>
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Legend() {
  const items = [
    { label: 'Số ca mắc', color: '#2563eb', shape: 'square' as const },
    { label: 'Nhiệt độ', color: '#0f766e', shape: 'line' as const },
    { label: 'Độ ẩm', color: '#92400e', shape: 'line' as const },
    { label: 'Lượng mưa', color: '#3b82f6', shape: 'line' as const, dashed: true },
    { label: 'AQI', color: '#dc2626', shape: 'line' as const },
    { label: 'PM2.5', color: '#334155', shape: 'line' as const },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-neutral-600">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          {it.shape === 'square' ? (
            <span
              className="w-2.5 h-2.5 rounded-sm shrink-0"
              style={{ backgroundColor: it.color }}
            />
          ) : (
            <span
              className="w-3 h-0.5 shrink-0"
              style={{
                backgroundColor: it.color,
                ...(it.dashed
                  ? { backgroundImage: `linear-gradient(90deg, ${it.color} 60%, transparent 0)`, backgroundSize: '6px 2px', backgroundColor: 'transparent' }
                  : {}),
              }}
            />
          )}
          {it.label}
        </span>
      ))}
    </div>
  );
}
