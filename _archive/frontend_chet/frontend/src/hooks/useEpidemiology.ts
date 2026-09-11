import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { epidemiologyService } from '../services/epidemiologyService';
import type { DiseaseCaseCreate, DiseaseType } from '../types/epidemiology';

export function useDiseaseCases(params?: {
  skip?: number;
  limit?: number;
  disease_type?: DiseaseType;
  location?: string;
}) {
  return useQuery({
    queryKey: ['disease-cases', params],
    queryFn: () => epidemiologyService.getDiseaseCases(params),
  });
}

export function useCreateDiseaseCase() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: DiseaseCaseCreate) =>
      epidemiologyService.createDiseaseCase(data),
    onSuccess: () => {
      // Invalidate and refetch disease case queries
      queryClient.invalidateQueries({ queryKey: ['disease-cases'] });
      queryClient.invalidateQueries({ queryKey: ['disease-stats'] });
      queryClient.invalidateQueries({ queryKey: ['disease-trends'] });
    },
  });
}

export function useDiseaseStatistics(params?: {
  location?: string;
  start_date?: string;
  end_date?: string;
}) {
  return useQuery({
    queryKey: ['disease-stats', params],
    queryFn: () => epidemiologyService.getStatistics(params),
  });
}

export function useDiseaseTrends(params?: {
  disease_type?: DiseaseType;
  location?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ['disease-trends', params],
    queryFn: () => epidemiologyService.getTrends(params),
  });
}
