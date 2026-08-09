import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface ComparisonItem {
  year: number;
  value: number;
  is_forecast: boolean;
}

interface Props {
  data: ComparisonItem[];
  targetMonth: number;
}

export default function ComparisonChart({ data, targetMonth }: Props) {
  const formatted = data.map((d) => ({
    label: String(d.year),
    value: d.value,
    is_forecast: d.is_forecast,
  }));

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex items-start justify-between mb-4 gap-4">
        <h3 className="text-sm font-semibold text-neutral-900">
          So sánh số ca bệnh cùng kỳ (Tháng {targetMonth})
        </h3>
        <span className="inline-flex items-center gap-1.5 text-xs text-neutral-600">
          <span className="w-2 h-2 rounded-sm bg-blue-600" />
          Số ca bệnh
        </span>
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={formatted} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="#9ca3af"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
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
              formatter={(v: number) => [v.toLocaleString('vi-VN') + ' ca', 'Số ca']}
            />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={36}>
              {formatted.map((d, idx) => (
                <Cell
                  key={idx}
                  fill={d.is_forecast ? '#2563eb' : '#bfdbfe'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
