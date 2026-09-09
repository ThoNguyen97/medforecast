import Card, { CardHeader } from '../common/Card';
import Badge from '../common/Badge';
import type { DiseaseCase } from '../../types/epidemiology';
import { DISEASE_TYPE_LABELS } from '../../types/epidemiology';

interface RecentCasesTableProps {
  cases: DiseaseCase[];
  isLoading?: boolean;
}

const getDiseaseTypeBadgeColor = (diseaseType: string) => {
  switch (diseaseType) {
    case 'dengue_fever':
      return 'danger';
    case 'seasonal_flu':
      return 'primary';
    case 'respiratory_disease':
      return 'warning';
    default:
      return 'neutral';
  }
};

export default function RecentCasesTable({ cases, isLoading }: RecentCasesTableProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader title="Ca bệnh Gần đây" subtitle="Dữ liệu ca bệnh mới nhất" />
        <div className="flex items-center justify-center h-48 text-neutral-400 text-sm">
          Đang tải...
        </div>
      </Card>
    );
  }

  return (
    <Card padding="none">
      <div className="p-6 pb-4">
        <CardHeader
          title="Ca bệnh Gần đây"
          subtitle="Dữ liệu ca bệnh mới nhất"
          className="mb-0"
        />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-neutral-50 border-y border-neutral-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                Ngày ghi nhận
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                Loại dịch bệnh
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                Số ca
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                Địa điểm
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                Mức độ
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                Nguồn dữ liệu
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-neutral-200">
            {cases.length > 0 ? (
              cases.map((caseItem) => (
                <tr key={caseItem.id} className="hover:bg-neutral-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-900">
                    {new Date(caseItem.recorded_at).toLocaleDateString('vi-VN', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                    })}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={getDiseaseTypeBadgeColor(caseItem.disease_type)}>
                      {DISEASE_TYPE_LABELS[caseItem.disease_type]}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-neutral-900">
                    {caseItem.case_count.toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-600">
                    {caseItem.location}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-600">
                    {caseItem.severity || '—'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-neutral-500">
                    {caseItem.data_source || '—'}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td
                  colSpan={6}
                  className="px-6 py-12 text-center text-sm text-neutral-400"
                >
                  Không có dữ liệu ca bệnh
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
