import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Props {
  data: Array<{ month: string; value: number }>;
  targetYear: number;
  upToMonth: number;
}

export default function CurrentYearTrendChart({
  data,
  targetYear,
  upToMonth,
}: Props) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex items-start justify-between mb-4 gap-4">
        <h3 className="text-sm font-semibold text-neutral-900">
          Xu hướng số ca bệnh năm {targetYear} (Đến T{upToMonth})
        </h3>
        <span className="inline-flex items-center gap-1.5 text-xs text-neutral-600">
          <span className="w-2 h-2 rounded-full bg-blue-600" />
          Thực tế
        </span>
      </div>

      <div className="h-64">
        {data.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-neutral-400">
            Chưa có dữ liệu cho năm {targetYear}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="month"
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
              <Line
                type="monotone"
                dataKey="value"
                stroke="#2563eb"
                strokeWidth={2.5}
                dot={{ r: 3, fill: '#2563eb' }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
