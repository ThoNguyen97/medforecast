import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { INK } from '../../utils/chartTheme';
import { LEVEL_HEX } from './LevelPill';
import type { AlertLevel, DoiCategory, Thresholds } from '../../types/dashboardV2';

function levelOf(doi: number | null, th: Thresholds): AlertLevel {
  if (doi == null) return 'grey';
  if (doi <= th.red_days) return 'red';
  if (doi <= th.amber_days) return 'amber';
  return 'green';
}

/**
 * Số ngày tồn phủ nhu cầu (DOI trung vị) theo danh mục vật tư, thanh ngang,
 * hai vạch ngưỡng Đỏ/Vàng. Màu thanh = mức của trung vị, luôn kèm số ở đầu
 * thanh và số mã Đỏ trong tooltip — màu không mang nghĩa một mình.
 */
export default function DoiCategoryChart({
  data,
  thresholds,
}: {
  data: DoiCategory[];
  thresholds: Thresholds;
}) {
  const rows = data
    .filter((d) => d.median_doi != null)
    .map((d) => ({ ...d, level: levelOf(d.median_doi, thresholds) }));
  const chuaDo = data.filter((d) => d.median_doi == null);

  if (rows.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center text-sm text-neutral-400">
        Chưa đo được DOI cho danh mục nào.
      </div>
    );
  }

  const maxDoi = Math.max(thresholds.amber_days * 1.2, ...rows.map((r) => r.median_doi ?? 0));
  const height = Math.max(200, rows.length * 34 + 24);

  return (
    <div>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 4 }} barCategoryGap={8}>
            <XAxis
              type="number"
              domain={[0, Math.ceil(maxDoi / 10) * 10]}
              tickLine={false}
              axisLine={false}
              tick={{ fill: INK.axis, fontSize: 11 }}
              unit=" ng"
            />
            <YAxis
              type="category"
              dataKey="category"
              width={118}
              tickLine={false}
              axisLine={false}
              tick={{ fill: '#374151', fontSize: 11.5 }}
              interval={0}
            />
            <Tooltip content={<DoiTooltip />} cursor={{ fill: 'rgba(148,163,184,0.10)' }} />
            <ReferenceLine
              x={thresholds.red_days}
              stroke={LEVEL_HEX.red}
              strokeDasharray="3 3"
              label={{ value: `Đỏ ≤ ${thresholds.red_days}`, position: 'insideTopRight', fontSize: 10, fill: LEVEL_HEX.red }}
            />
            <ReferenceLine
              x={thresholds.amber_days}
              stroke={LEVEL_HEX.amber}
              strokeDasharray="3 3"
              label={{ value: `Vàng ≤ ${thresholds.amber_days}`, position: 'insideTopRight', fontSize: 10, fill: '#a16207' }}
            />
            <Bar dataKey="median_doi" radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.category} fill={LEVEL_HEX[r.level]} />
              ))}
              <LabelList
                dataKey="median_doi"
                position="right"
                formatter={(v: number) => `${v.toLocaleString('vi-VN', { maximumFractionDigits: 1 })}`}
                style={{ fontSize: 11, fill: '#0b0b0b', fontWeight: 600 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[11px] text-neutral-500">
        DOI trung vị của các mã đo được trong danh mục (ngày). Thanh Đỏ/Vàng/Xanh theo ngưỡng của trung vị.
        {chuaDo.length > 0 && (
          <>
            {' '}Chưa đo được: {chuaDo.map((d) => `${d.category} (${d.n})`).join(', ')}.
          </>
        )}
      </p>
    </div>
  );
}

function DoiTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: DoiCategory & { level: AlertLevel } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white border border-neutral-200 rounded-lg shadow-sm px-3 py-2 text-xs">
      <div className="font-semibold text-neutral-900 mb-1">{d.category}</div>
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-neutral-700">
        <span>DOI trung vị</span>
        <span className="text-right tabular-nums font-medium">{d.median_doi} ngày</span>
        <span>Đo được / tổng</span>
        <span className="text-right tabular-nums">
          {d.n_measured} / {d.n} mã
        </span>
        <span>Đỏ · Vàng · Xanh · Xám</span>
        <span className="text-right tabular-nums">
          {d.red} · {d.amber} · {d.green} · {d.grey}
        </span>
      </div>
    </div>
  );
}
