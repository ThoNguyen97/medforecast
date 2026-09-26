import { useMutation, useQuery } from '@tanstack/react-query';
import {
  forecastAnalysisService,
  type AnalyzeRequest,
  type AnalyzeResponse,
} from '../services/forecastAnalysisService';
import { useAuthStore } from '../store/authStore';

export function useDiseaseOptions() {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['forecast', 'diseases'],
    queryFn: () => forecastAnalysisService.listDiseases(),
    enabled: isAuthenticated,
    staleTime: 10 * 60 * 1000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useRegionOptions() {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['forecast', 'regions'],
    queryFn: () => forecastAnalysisService.listRegions(),
    enabled: isAuthenticated,
    staleTime: 10 * 60 * 1000,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useAnalyzeForecast() {
  return useMutation<AnalyzeResponse, Error, AnalyzeRequest>({
    mutationFn: (payload) => forecastAnalysisService.analyze(payload),
  });
}

/** Nạp bản dự báo đã ghi nhận theo khóa. Dùng useQuery thay vì useMutation:
 *  mutation gọi trong useEffect hỏng dưới StrictMode (isPending kẹt true). */
export function useSavedForecast(
  p: {
    disease_type: string;
    region: string | null;
    target_month: number;
    target_year: number;
  } | null,
) {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: [
      'forecast',
      'saved',
      p?.disease_type,
      p?.region,
      p?.target_month,
      p?.target_year,
    ],
    queryFn: () => forecastAnalysisService.loadSaved(p!),
    enabled: isAuthenticated && !!p,
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useForecastHistory(
  params?: {
    limit?: number;
    disease_type?: string;
    region?: string;
    start_date?: string;
    end_date?: string;
  },
  options?: { enabled?: boolean },
) {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['forecast', 'history', params],
    queryFn: () => forecastAnalysisService.getHistory(params),
    enabled: isAuthenticated && (options?.enabled ?? true),
    retry: false,
    refetchOnWindowFocus: false,
  });
}
