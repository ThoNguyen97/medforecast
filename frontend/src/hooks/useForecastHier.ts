import { useQuery } from '@tanstack/react-query';
import { forecastHierService } from '../services/forecastHierService';
import { useAuthStore } from '../store/authStore';

export function useHierForecast(block: string, method = 'top_down_dynamic') {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['forecast-hier', block, method],
    queryFn: () => forecastHierService.forecast(block, method),
    enabled: isAuthenticated && !!block,
    staleTime: 60_000,
    retry: false,
  });
}
