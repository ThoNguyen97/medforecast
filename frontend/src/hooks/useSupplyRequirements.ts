import { useQuery } from '@tanstack/react-query';
import { supplyRequirementsService } from '../services/supplyRequirementsService';
import { useAuthStore } from '../store/authStore';

export function useSupplyRequirementsSummary(params?: {
  disease_type?: string;
  category?: string;
  start_date?: string;
  end_date?: string;
}) {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['supply-requirements', 'summary', params],
    queryFn: () => supplyRequirementsService.getSummary(params),
    enabled: isAuthenticated,
    retry: false,
    refetchOnWindowFocus: false,
  });
}
