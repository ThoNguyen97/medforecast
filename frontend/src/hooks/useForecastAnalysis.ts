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

/**
 * Nạp bản dự báo ĐÃ GHI NHẬN theo khóa (nhóm bệnh, khu vực, tháng).
 *
 * Cố ý dùng useQuery chứ không phải useMutation: đây là thao tác ĐỌC, chạy tự
 * động theo bộ lọc. Dùng mutation trong useEffect lúc mount sẽ hỏng dưới
 * <StrictMode> — React chạy effect, huỷ, rồi chạy lại; React Query gỡ observer
 * khỏi mutation đang bay nên kết quả không bao giờ về tới component và
 * isPending kẹt true vĩnh viễn.
 *
 * queryKey tách thành từng giá trị nguyên thuỷ (không truyền cả object) để
 * key không đổi sau mỗi lần render.
 */
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
