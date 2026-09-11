import { useMemo } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { INK, SERIES, gridProps } from '../../utils/chartTheme';
import type { BlockCode, ForecastSummary, TrendSection } from '../../types/dashboardV2';

interface Row {
  key: string;
  period: string;
  month: string;
  nam_nay: number | null;
  /** Kỳ đang mở: vẽ nét đứt nối từ kỳ chốt cuối, không nối nét liền. */
  nam_nay_mo: number | null;
  nam_truoc: number | null;
  chua_chot: boolean;
  du_bao: number | null;
  khoang: [number, number] | null;
  la_du_bao: boolean;
}

function monthLabel(period: string) {
  return `T${parseInt(period.slice(5, 7), 10)}`;
}

/**
 * Xu hướng ca bệnh 12 kỳ, năm nay so với cùng kỳ năm trước, kèm điểm dự báo
 * kỳ tới và dải khoảng tin cậy. Kỳ đang mở được đánh dấu "chưa chốt" và KHÔNG
 * nối vào đường năm nay bằng nét liền — cột đó là số đang thu thập dở.
 */
export default function TrendChart({
  trend,
  forecast,
  block,
}: {
  trend: TrendSection;
  forecast: ForecastSummary;
  block: BlockCode | 'all';
}) {
  const rows = useMemo<Row[]>(() => {
    const thisYear = block === 'all' ? trend.total : trend.by_block[block] ?? [];
    const lastYear = block === 'all' ? trend.last_year.total : trend.last_year.by_block[block] ?? [];
    const fcBlock = block === 'all' ? null : forecast.blocks.find((b) => b.block === block) ?? null;
    const fcPoint = forecast.ready
      ? block === 'all'
        ? forecast.total.point
        : fcBlock?.point ?? null
      : null;
    const fcLo = block === 'all' ? forecast.total.lower : fcBlock?.lower ?? null;
    const fcHi = block === 'all' ? forecast.total.upper : fcBlock?.upper ?? null;
    const target = forecast.target_period;

    const out: Row[] = thisYear.map((p, i) => ({
      key: p.period,
      period: p.period,
      month: monthLabel(p.period) + (p.is_complete === false ? '*' : ''),
      nam_nay: p.is_complete === false ? null : p.cases,
      nam_nay_mo: p.is_complete === false ? p.cases : null,
      nam_truoc: lastYear[i]?.cases ?? null,
      chua_chot: p.is_complete === false,
      du_bao: null,
      khoang: null,
      la_du_bao: false,
    }));

    // Điểm neo: kỳ đã chốt cuối cùng → nét đứt sang kỳ đang mở và kỳ dự báo.
    const anchorIdx = [...out].map((r) => !r.chua_chot).lastIndexOf(true);
    if (anchorIdx >= 0) {
      const a = out[anchorIdx];
      if (out.some((r) => r.chua_chot)) a.nam_nay_mo = a.nam_nay;
    }
    if (fcPoint == null || !target) return out;
    if (anchorIdx >= 0) {
      const a = out[anchorIdx];
      a.du_bao = a.nam_nay;
      if (fcLo != null && fcHi != null && a.nam_nay != null) a.khoang = [a.nam_nay, a.nam_nay];
    }
    const existing = out.find((r) => r.period === target);
    if (existing) {
      existing.du_bao = Math.round(fcPoint);
      existing.khoang = fcLo != null && fcHi != null ? [fcLo, fcHi] : null;
      existing.la_du_bao = true;
    } else {
      out.push({
        key: target,
        period: target,
        month: monthLabel(target) + '†',
        nam_nay: null,
        nam_nay_mo: null,
        nam_truoc: null,
        chua_chot: false,
        du_bao: Math.round(fcPoint),
        khoang: fcLo != null && fcHi != null ? [fcLo, fcHi] : null,
        la_du_bao: true,
      });
    }
    return out;
  }, [trend, forecast, block]);

  if (rows.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center text-sm text-neutral-400">
        Chưa có dữ liệu xu hướng — hãy đồng bộ HIS.
      </div>
    );
  }

  const hasBand = rows.some((r) => r.khoang);

  return (
    <div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={false}
              tick={{ fill: INK.axis, fontSize: 11 }}
              interval={0}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: INK.axis, fontSize: 11 }}
              width={40}
              allowDecimals={false}
            />
            <Tooltip content={<TrendTooltip />} cursor={{ stroke: '#cbd5e1', strokeWidth: 1 }} />
            {hasBand && (
              <Area
                type="monotone"
                dataKey="khoang"
                stroke="none"
                fill={SERIES.s1}
                fillOpacity={0.14}
                connectNulls={false}
                isAnimationActive={false}
                activeDot={false}
                dot={false}
              />
            )}
            <Line
              type="monotone"
              dataKey="nam_truoc"
              stroke={INK.reference}
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
              activeDot={{ r: 4, fill: INK.reference, stroke: '#fff', strokeWidth: 2 }}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="nam_nay"
              stroke={SERIES.s1}
              strokeWidth={2.5}
              dot={{ r: 3, strokeWidth: 2, stroke: '#ffffff', fill: SERIES.s1 }}
              activeDot={{ r: 5 }}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="nam_nay_mo"
              stroke={SERIES.s1}
              strokeWidth={2}
              strokeDasharray="2 3"
              dot={(props: { cx?: number; cy?: number; payload?: Row; index?: number }) => {
                const { cx, cy, payload, index } = props;
                if (cx == null || cy == null || !payload?.chua_chot) return <g key={index} />;
                return <circle key={index} cx={cx} cy={cy} r={4} fill="#fff" stroke={SERIES.s1} strokeWidth={2} />;
              }}
              activeDot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="du_bao"
              stroke={SERIES.s1}
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={(props: { cx?: number; cy?: number; payload?: Row; index?: number }) => {
                const { cx, cy, payload, index } = props;
                if (cx == null || cy == null || !payload?.la_du_bao) return <g key={index} />;
                return (
                  <g key={index}>
                    <circle cx={cx} cy={cy} r={5} fill="#fff" stroke={SERIES.s1} strokeWidth={2.5} />
                    <text x={cx} y={cy - 11} textAnchor="middle" fontSize={11} fontWeight={600} fill="#0b0b0b">
                      {payload.du_bao?.toLocaleString('vi-VN')}
                    </text>
                  </g>
                );
              }}
              activeDot={false}
              connectNulls
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-neutral-500">
        <LegendItem swatch={<span className="w-4 h-0.5 rounded" style={{ background: SERIES.s1 }} />} label="Năm nay (đã chốt)" />
        <LegendItem
          swatch={<span className="w-4 h-0.5 rounded border-t-2 border-dashed" style={{ borderColor: INK.reference }} />}
          label="Cùng kỳ năm trước"
        />
        <LegendItem
          swatch={<span className="w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: SERIES.s1 }} />}
          label="Dự báo"
        />
        {hasBand && (
          <LegendItem
            swatch={<span className="w-4 h-2.5 rounded-sm" style={{ background: SERIES.s1, opacity: 0.18 }} />}
            label={`Khoảng ${Math.round(forecast.level * 100)}%`}
          />
        )}
        <span className="ml-auto">* kỳ chưa chốt</span>
      </div>
    </div>
  );
}

function LegendItem({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {swatch}
      {label}
    </span>
  );
}

function TrendTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Row }> }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const fmt = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString('vi-VN'));
  return (
    <div className="bg-white border border-neutral-200 rounded-lg shadow-sm px-3 py-2 text-xs">
      <div className="font-semibold text-neutral-900 mb-1">
        Kỳ {r.period}
        {r.chua_chot && <span className="ml-1.5 text-[10px] font-medium text-amber-700">chưa chốt</span>}
      </div>
      <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-neutral-700">
        <span>Năm nay</span>
        <span className="text-right tabular-nums font-medium">{fmt(r.nam_nay ?? r.nam_nay_mo)}</span>
        <span>Năm trước</span>
        <span className="text-right tabular-nums">{fmt(r.nam_truoc)}</span>
        {r.la_du_bao && (
          <>
            <span>Dự báo</span>
            <span className="text-right tabular-nums font-medium">{fmt(r.du_bao)}</span>
            {r.khoang && (
              <>
                <span>Khoảng</span>
                <span className="text-right tabular-nums">
                  {fmt(r.khoang[0])}–{fmt(r.khoang[1])}
                </span>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
