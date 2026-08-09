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

// Năm là dữ liệu CÓ THỨ TỰ → mã hóa bằng ramp tuần tự một tông (nhạt = xa, đậm = gần);
// năm hiện tại nổi bật bằng màu series chính. (Chuẩn dataviz: sequential cho magnitude/thứ tự.)
const COLOR_PALETTE = ['#d3dce6', '#b1c4d8', '#8dabca', '#6892bd', '#40729f', '#2a78d6'];

export default function ForecastVsActualChart({
  data,
  years,
  targetYear,
  targetMonth,
}: Props) {
  const colorMap = mapYearsToColors(years, targetYear);
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

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex items-start justify-between mb-4 gap-4">
        <h3 className="text-sm font-semibold text-neutral-900">
          Biểu đồ dự báo so với thực tế
        </h3>
        <Legend years={years} targetYear={targetYear} colorMap={colorMap} />
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
              content={<CustomTooltip targetYear={targetYear} />}
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
            {years.map((y) => {
              const color = colorMap[y];
              const isTarget = y === targetYear;
              if (isTarget) {
                // Năm hiện tại: chia 2 line — actual nét liền, forecast nét đứt
                return [
                  <Line
                    key={`${y}-actual`}
                    type="monotone"
                    dataKey={`${y}_actual_line`}
                    name={`${y} (Hiện tại)`}
                    stroke={color}
                    strokeWidth={3}
                    dot={{ r: 4, fill: color }}
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
                    stroke={color}
                    strokeWidth={3}
                    strokeDasharray="6 4"
                    dot={{ r: 4, fill: color }}
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
                  stroke={color}
                  strokeWidth={2}
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

function mapYearsToColors(years: number[], targetYear: number): Record<number, string> {
  // Năm hiện tại luôn màu xanh đậm; các năm còn lại đi theo palette từ nhạt → đậm.
  const sorted = [...years].sort((a, b) => a - b);
  const others = sorted.filter((y) => y !== targetYear);
  const map: Record<number, string> = {};

  others.forEach((y, idx) => {
    map[y] = COLOR_PALETTE[idx] ?? COLOR_PALETTE[COLOR_PALETTE.length - 2];
  });
  map[targetYear] = COLOR_PALETTE[COLOR_PALETTE.length - 1];
  return map;
}

function Legend({
  years,
  targetYear,
  colorMap,
}: {
  years: number[];
  targetYear: number;
  colorMap: Record<number, string>;
}) {
  const sorted = [...years].sort((a, b) => a - b);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-neutral-600">
      {sorted.map((y) => {
        const isTarget = y === targetYear;
        return (
          <span key={y} className="inline-flex items-center gap-1.5">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: colorMap[y] }}
            />
            {y}
            {isTarget && <span className="text-neutral-400">(Hiện tại)</span>}
          </span>
        );
      })}
    </div>
  );
}

function CustomTooltip({ active, payload, label, targetYear }: any) {
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

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-3 shadow-lg">
      <p className="font-semibold text-neutral-900 mb-2">{label}</p>
      {Array.from(years).map((year) => {
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
          
          return (
            <div key={year} className="flex items-center justify-between gap-4 text-sm">
              <span style={{ color }}>{year}:</span>
              <span className="font-medium">{value}</span>
            </div>
          );
        }
      })}
    </div>
  );
}
