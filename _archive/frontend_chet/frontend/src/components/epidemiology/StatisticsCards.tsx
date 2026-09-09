import { Activity, TrendingUp, Calendar } from 'lucide-react';
import { MetricCard } from '../common/Card';
import type { DiseaseStatistic } from '../../types/epidemiology';
import { DISEASE_TYPE_LABELS } from '../../types/epidemiology';

interface StatisticsCardsProps {
  statistics: DiseaseStatistic[];
}

export default function StatisticsCards({ statistics }: StatisticsCardsProps) {
  // Calculate total cases across all disease types
  const totalCases = statistics.reduce((sum, stat) => sum + stat.total_cases, 0);

  // Find the disease with the highest case count
  const highestDiseaseType = statistics.reduce(
    (max, stat) => (stat.total_cases > max.total_cases ? stat : max),
    statistics[0] || { disease_type: 'dengue_fever', total_cases: 0 }
  );

  // Calculate average cases per day across all diseases
  const avgCasesPerDay = statistics.reduce(
    (sum, stat) => sum + (stat.avg_cases_per_day || 0),
    0
  );

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      <MetricCard
        title="Tổng ca bệnh"
        value={totalCases.toLocaleString()}
        subtitle="Tất cả loại dịch bệnh"
        icon={<Activity size={24} />}
        color="primary"
      />
      <MetricCard
        title="Loại dịch bệnh"
        value={statistics.length}
        subtitle="Đang theo dõi"
        icon={<Calendar size={24} />}
        color="success"
      />
      <MetricCard
        title="Dịch bệnh cao nhất"
        value={highestDiseaseType.total_cases.toLocaleString()}
        subtitle={DISEASE_TYPE_LABELS[highestDiseaseType.disease_type]}
        icon={<TrendingUp size={24} />}
        color="warning"
      />
      <MetricCard
        title="Trung bình/ngày"
        value={Math.round(avgCasesPerDay).toLocaleString()}
        subtitle="Ca bệnh mỗi ngày"
        icon={<Activity size={24} />}
        color="neutral"
      />
    </div>
  );
}
