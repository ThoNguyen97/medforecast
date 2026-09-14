import { useQuery } from '@tanstack/react-query';
import { supplyRequirementsService } from '../services/supplyRequirementsService';
import { useAuthStore } from '../store/authStore';

/** Tóm tắt thiếu hụt cho báo cáo — cùng chuỗi DSS với trang Cảnh báo. */
export function useSupplyRequirementsSummary(
  params?: { disease_type?: string; category?: string },
  options?: { enabled?: boolean },
) {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['supply-requirements', 'summary', params],
    queryFn: () => supplyRequirementsService.getSummary(params),
    enabled: isAuthenticated && (options?.enabled ?? true),
    retry: false,
    refetchOnWindowFocus: false,
  });
}
