import { useMutation, useQuery } from '@tanstack/react-query';
import {
  forecastAnalysisService,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type MLAnalyzeResponse,
  type TrainResponse,
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

/** Nạp bản dự báo đã ghi nhận (chỉ đọc) — dùng khi mở trang / đổi bộ lọc. */
export function useLoadSavedForecast() {
  return useMutation<AnalyzeResponse | null, Error, AnalyzeRequest>({
    mutationFn: (payload) => forecastAnalysisService.loadSaved(payload),
  });
}

export function useTrainModels() {
  return useMutation<TrainResponse, Error, string | null | undefined>({
    mutationFn: (region) => forecastAnalysisService.trainModels(region),
  });
}

export function useMLAnalyzeForecast() {
  return useMutation<MLAnalyzeResponse, Error, AnalyzeRequest>({
    mutationFn: (payload) => forecastAnalysisService.mlAnalyze(payload),
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
