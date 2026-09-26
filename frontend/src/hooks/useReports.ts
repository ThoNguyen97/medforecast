import { useQuery } from '@tanstack/react-query';
import { reportsService } from '../services/reportsService';
import type { ReportFilters } from '../types/reports';

/** Xem trước độ chính xác dự báo; chỉ gọi API khi `enabled`. */
export function useForecastAccuracyReport(filters?: ReportFilters, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['reports', 'forecast-accuracy', filters],
    queryFn: () => reportsService.getForecastAccuracyReport(filters),
    staleTime: 2 * 60 * 1000,
    enabled: options?.enabled ?? true,
  });
}
