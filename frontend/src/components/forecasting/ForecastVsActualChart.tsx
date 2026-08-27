import { useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Props {
  data: Array<Record<string, number | string>>;
  years: number[];
  targetYear: number;
  targetMonth: number;
}

// Chiến lược màu: năm hiện tại và năm liền trước — 2 năm cần SO SÁNH TRỰC TIẾP
// nhất — dùng xanh/cam đậm, nét dày, luôn nổi bật. Các năm cũ hơn (2+ năm
// trước) mỗi năm có 1 màu RIÊNG BIỆT (không dùng chung 1 màu xám nữa — xám
// đơn sắc khiến các năm cũ gần như vô hình/khó nhìn). Bộ màu lấy theo đúng
// thứ tự categorical đã kiểm định chống mù màu (xem dataviz skill —
// color-formula.md): 1 xanh dương, 2 cam đã dùng cho target/prev; các năm cũ
// nối tiếp slot 3-8 (ngọc lam, vàng, hồng cánh sen, lục, tím, đỏ) theo đúng
// thứ tự cố định đó, không đảo lộn. Rê chuột / bấm vào chú thích vẫn cô lập
// được 1 năm cụ thể để xem rõ hơn khi các đường chồng lên nhau.
const COLOR_TARGET = '#2a78d6'; // năm hiện tại — slot 1 (xanh dương)
const COLOR_PREV = '#eb6834'; // năm liền trước — slot 2 (cam)
// Slot 3-8: ngọc lam, vàng, hồng cánh sen, lục, tím, đỏ — mỗi năm cũ 1 màu.
const HISTORY_PALETTE = [
  '#1baf7a', // ngọc lam
  '#eda100', // vàng
  '#e87ba4', // hồng cánh sen
  '#008300', // lục
  '#4a3aa7', // tím
  '#e34948', // đỏ
];

type YearRole = 'target' | 'prev' | 'history';

function roleOfYear(year: number, targetYear: number, prevYear: number): YearRole {
  if (year === targetYear) return 'target';
  if (year === prevYear) return 'prev';
  return 'history';
}

export default function ForecastVsActualChart({
  data,
  years,
  targetYear,
  targetMonth,
}: Props) {
  // Năm đang được "cô lập" để xem riêng — hoverYear là preview khi rê chuột,
  // lockedYear giữ nguyên sau khi bấm (để dùng được cả trên di động/màn cảm ứng).
  const [hoverYear, setHoverYear] = useState<number | null>(null);
  const [lockedYear, setLockedYear] = useState<number | null>(null);
  const activeYear = lockedYear ?? hoverYear;

  const sortedYears = [...years].sort((a, b) => a - b);
  const prevYear = targetYear - 1;
  const hasPrevYear = sortedYears.includes(prevYear);
  const historyYears = sortedYears.filter((y) => y !== targetYear && y !== prevYear);
  // Vẽ năm cũ trước (nằm dưới), năm liền trước rồi năm hiện tại vẽ sau cùng
  // (nằm trên) — để 2 đường quan trọng nhất không bao giờ bị đường khác che.
  const renderOrder = [
    ...historyYears,
    ...(hasPrevYear ? [prevYear] : []),
    ...(sortedYears.includes(targetYear) ? [targetYear] : []),
  ];

  // Mỗi năm 1 màu cố định trong lần render này — năm cũ lấy lần lượt từ
  // HISTORY_PALETTE theo thứ tự tăng dần (2021 → màu đầu tiên, 2022 → màu kế...).
  const yearColor: Record<number, string> = {};
  historyYears.forEach((y, idx) => {
    yearColor[y] = HISTORY_PALETTE[idx % HISTORY_PALETTE.length];
  });
  if (hasPrevYear) yearColor[prevYear] = COLOR_PREV;
  if (sortedYears.includes(targetYear)) yearColor[targetYear] = COLOR_TARGET;

  const targetMonthKey = `T${targetMonth}`;

  // Backend đã trả về 2 fields riêng: <year>_actual và <year>_forecast
  // - <year>_actual: số ca thực tế (dùng cho tooltip và vẽ đường actual)
  // - <year>_forecast: số ca dự báo đã lưu (dùng cho tooltip)
  // - <year>_forecast_line: dùng để VẼ đường nét đứt (T5 lấy actual, T6 lấy forecast)
  const targetKey = String(targetYear);
  const enriched = data.map((row, idx) => {
    const monthIdx = idx + 1; // T1 = idx 0
    const isForecastMonth = monthIdx === targetMonth;
    const isLastActual = monthIdx === targetMonth - 1;

    const actualValue = row[`${targetKey}_actual`];
    const forecastValue = row[`${targetKey}_forecast`];

    return {
      ...row,
      // Giữ nguyên actual và forecast cho tooltip
      [`${targetKey}_actual`]: actualValue,
      [`${targetKey}_forecast`]: forecastValue,
      // Tạo riêng field để vẽ đường
      [`${targetKey}_actual_line`]: isForecastMonth ? null : actualValue,
      [`${targetKey}_forecast_line`]:
        isLastActual ? actualValue : (isForecastMonth ? forecastValue : null),
    };
  });

  // Độ dày/độ mờ của 1 đường, tuỳ theo vai trò (target/prev/history) và việc
  // có năm nào đang được cô lập (activeYear) hay không. Màu lấy từ yearColor —
  // mỗi năm cũ giờ có màu riêng, không còn dùng chung 1 màu xám nữa.
  const lineStyleOf = (year: number) => {
    const role = roleOfYear(year, targetYear, prevYear);
    const isDimmed = activeYear !== null && activeYear !== year;
    const isFocused = activeYear === year;

    const color = yearColor[year] ?? HISTORY_PALETTE[0];

    let width = 1.6;
    if (role === 'target') width = 3;
    else if (role === 'prev') width = 2.25;
    else if (isFocused) width = 2.25;

    let opacity = 0.85;
    if (role === 'target' || role === 'prev' || isFocused) opacity = 1;
    if (isDimmed) opacity = 0.12;

    return { color, width, opacity };
  };

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex items-start justify-between mb-4 gap-4">
        <h3 className="text-sm font-semibold text-neutral-900">
          Biểu đồ dự báo so với thực tế
        </h3>
        <Legend
          years={sortedYears}
          targetYear={targetYear}
          prevYear={hasPrevYear ? prevYear : null}
          yearColor={yearColor}
          activeYear={activeYear}
          onHover={setHoverYear}
          onToggleLock={(y) => setLockedYear((cur) => (cur === y ? null : y))}
        />
      </div>

      <div className="h-72 sm:h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={enriched} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="month"
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              tickFormatter={(m) =>
                m === targetMonthKey ? `${m} (DB)` : m
              }
            />
            <YAxis
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              content={<CustomTooltip targetYear={targetYear} prevYear={prevYear} />}
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ fontWeight: 600 }}
            />
            <ReferenceLine
              x={targetMonthKey}
              stroke="#3b82f6"
              strokeDasharray="4 4"
              label={{
                value: 'Dự báo tháng tới',
                fill: '#3b82f6',
                fontSize: 11,
                position: 'insideTopRight',
              }}
            />
            {renderOrder.map((y) => {
              const isTarget = y === targetYear;
              const style = lineStyleOf(y);
              if (isTarget) {
                // Năm hiện tại: chia 2 line — actual nét liền, forecast nét đứt
                return [
                  <Line
                    key={`${y}-actual`}
                    type="monotone"
                    dataKey={`${y}_actual_line`}
                    name={`${y} (Hiện tại)`}
                    stroke={style.color}
                    strokeWidth={style.width}
                    strokeOpacity={style.opacity}
                    dot={{ r: 4, fill: style.color, fillOpacity: style.opacity }}
                    activeDot={{ r: 6 }}
                    connectNulls={false}
                    isAnimationActive
                    legendType="none"
                  />,
                  <Line
                    key={`${y}-forecast`}
                    type="monotone"
                    dataKey={`${y}_forecast_line`}
                    name={`${y} (Dự báo)`}
                    stroke={style.color}
                    strokeWidth={style.width}
                    strokeOpacity={style.opacity}
                    strokeDasharray="6 4"
                    dot={{ r: 4, fill: style.color, fillOpacity: style.opacity }}
                    activeDot={{ r: 6 }}
                    connectNulls={false}
                    isAnimationActive
                    legendType="none"
                  />,
                ];
              }
              return (
                <Line
                  key={y}
                  type="monotone"
                  dataKey={String(y)}
                  name={String(y)}
                  stroke={style.color}
                  strokeWidth={style.width}
                  strokeOpacity={style.opacity}
                  dot={false}
                  activeDot={{ r: 6 }}
                  isAnimationActive
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Legend({
  years,
  targetYear,
  prevYear,
  yearColor,
  activeYear,
  onHover,
  onToggleLock,
}: {
  years: number[];
  targetYear: number;
  prevYear: number | null;
  yearColor: Record<number, string>;
  activeYear: number | null;
  onHover: (y: number | null) => void;
  onToggleLock: (y: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-neutral-600">
      {years.map((y) => {
        const role = roleOfYear(y, targetYear, prevYear ?? -1);
        const isActive = activeYear === y;
        const isDimmed = activeYear !== null && !isActive;
        const swatchColor = yearColor[y] ?? HISTORY_PALETTE[0];

        return (
          <button
            key={y}
            type="button"
            onMouseEnter={() => onHover(y)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onToggleLock(y)}
            className={`inline-flex items-center gap-1.5 rounded-full px-1.5 py-0.5 transition-colors ${
              isActive ? 'bg-neutral-100 font-semibold text-neutral-900' : 'hover:bg-neutral-50'
            } ${isDimmed ? 'opacity-40' : ''}`}
            title="Bấm để xem riêng năm này"
          >
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: swatchColor }}
            />
            {y}
            {role === 'target' && <span className="text-neutral-400">(Hiện tại)</span>}
            {role === 'prev' && <span className="text-neutral-400">(Năm trước)</span>}
          </button>
        );
      })}
      <span className="text-[10px] text-neutral-400 italic ml-1">Bấm để xem riêng 1 năm</span>
    </div>
  );
}

function CustomTooltip({ active, payload, label, targetYear, prevYear }: any) {
  if (!active || !payload || !payload.length) return null;

  // Lọc ra các năm duy nhất từ payload
  const years = new Set<string>();
  payload.forEach((entry: any) => {
    const dataKey = entry.dataKey;
    // Lấy năm từ dataKey (bỏ hậu tố _actual, _forecast, _line)
    const year = dataKey.replace(/_actual_line|_forecast_line|_actual|_forecast/g, '');
    if (year && !isNaN(Number(year))) {
      years.add(year);
    }
  });

  // Sắp xếp: năm hiện tại lên đầu, kế đến năm liền trước, rồi các năm còn lại
  // giảm dần — vì đó là thứ tự người xem quan tâm khi so sánh.
  const sortedYearList = Array.from(years).sort((a, b) => {
    const rank = (y: string) => {
      if (Number(y) === targetYear) return 0;
      if (Number(y) === prevYear) return 1;
      return 2;
    };
    const ra = rank(a);
    const rb = rank(b);
    if (ra !== rb) return ra - rb;
    return Number(b) - Number(a);
  });

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-3 shadow-lg">
      <p className="font-semibold text-neutral-900 mb-2">{label}</p>
      {sortedYearList.map((year) => {
        const isTargetYear = year === String(targetYear);
        const color = payload.find((p: any) => p.dataKey.includes(year))?.color;

        if (isTargetYear) {
          // Năm target: hiển thị cả actual và forecast
          const dataPoint = payload[0]?.payload;
          if (!dataPoint) return null;

          const actualValue = dataPoint[`${year}_actual`];
          const forecastValue = dataPoint[`${year}_forecast`];

          return (
            <div key={year}>
              {actualValue !== null && actualValue !== undefined && (
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span style={{ color }}>
                    {year} (Hiện tại):
                  </span>
                  <span className="font-medium">{actualValue}</span>
                </div>
              )}
              {forecastValue !== null && forecastValue !== undefined && forecastValue !== 0 && (
                <div className="flex items-center justify-between gap-4 text-sm">
                  <span style={{ color }}>
                    {year} (Dự báo):
                  </span>
                  <span className="font-medium">{forecastValue}</span>
                </div>
              )}
            </div>
          );
        } else {
          // Các năm khác: hiển thị số ca thực tế
          const dataPoint = payload[0]?.payload;
          const value = dataPoint?.[year];

          if (value === null || value === undefined) return null;

          const label2 = year === String(prevYear) ? `${year} (Năm trước)` : year;

          return (
            <div key={year} className="flex items-center justify-between gap-4 text-sm">
              <span style={{ color }}>{label2}:</span>
              <span className="font-medium">{value}</span>
            </div>
          );
        }
      })}
    </div>
  );
}
