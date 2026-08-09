import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import Card, { CardHeader } from '../common/Card';
import type { DiseaseTrendPoint, DiseaseType } from '../../types/epidemiology';
import { DISEASE_TYPE_LABELS, DISEASE_TYPE_COLORS } from '../../types/epidemiology';

interface DiseaseTrendsChartProps {
  trends: DiseaseTrendPoint[];
  selectedDiseaseType?: DiseaseType;
}

export default function DiseaseTrendsChart({
  trends,
  selectedDiseaseType,
}: DiseaseTrendsChartProps) {
  // Group trends by date and disease type
  const chartData = trends.reduce((acc, trend) => {
    const date = new Date(trend.date).toLocaleDateString('vi-VN', {
      month: 'short',
      day: 'numeric',
    });
    
    const existingEntry = acc.find((entry) => entry.date === date);
    if (existingEntry) {
      existingEntry[trend.disease_type] = trend.case_count;
    } else {
      acc.push({
        date,
        fullDate: trend.date,
        [trend.disease_type]: trend.case_count,
      });
    }
    
    return acc;
  }, [] as Array<{ date: string; fullDate: string; [key: string]: any }>);

  // Sort by date
  chartData.sort((a, b) => new Date(a.fullDate).getTime() - new Date(b.fullDate).getTime());

  // Determine which disease types to show
  const diseaseTypes: DiseaseType[] = selectedDiseaseType
    ? [selectedDiseaseType]
    : ['dengue_fever', 'seasonal_flu', 'respiratory_disease'];

  return (
    <Card>
      <CardHeader
        title="Xu hướng Ca bệnh"
        subtitle="Biểu đồ theo dõi số ca bệnh theo thời gian"
      />
      <div className="h-80">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                stroke="#6b7280"
                style={{ fontSize: '12px' }}
              />
              <YAxis
                stroke="#6b7280"
                style={{ fontSize: '12px' }}
                label={{
                  value: 'Số ca bệnh',
                  angle: -90,
                  position: 'insideLeft',
                  style: { fontSize: '12px', fill: '#6b7280' },
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                labelStyle={{ color: '#111827', fontWeight: 600 }}
              />
              <Legend
                wrapperStyle={{ fontSize: '12px' }}
                formatter={(value) => DISEASE_TYPE_LABELS[value as DiseaseType] || value}
              />
              {diseaseTypes.map((diseaseType) => (
                <Line
                  key={diseaseType}
                  type="monotone"
                  dataKey={diseaseType}
                  stroke={DISEASE_TYPE_COLORS[diseaseType]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  name={diseaseType}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-neutral-400 text-sm">
            Không có dữ liệu xu hướng
          </div>
        )}
      </div>
    </Card>
  );
}
