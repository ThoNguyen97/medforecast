import { useQuery } from '@tanstack/react-query';
import { reportsService } from '../services/reportsService';
import type { ReportFilters } from '../types/reports';

/**
 * Hook for consumption report data.
 * Re-fetches whenever `filters` changes.
 */
export function useConsumptionReport(filters?: ReportFilters) {
  return useQuery({
    queryKey: ['reports', 'consumption', filters],
    queryFn: () => reportsService.getConsumptionReport(filters),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook for forecast accuracy report data.
 */
export function useForecastAccuracyReport(filters?: ReportFilters) {
  return useQuery({
    queryKey: ['reports', 'forecast-accuracy', filters],
    queryFn: () => reportsService.getForecastAccuracyReport(filters),
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Hook for inventory turnover report data.
 */
export function useInventoryTurnoverReport(filters?: ReportFilters) {
  return useQuery({
    queryKey: ['reports', 'inventory-turnover', filters],
    queryFn: () => reportsService.getInventoryTurnoverReport(filters),
    staleTime: 2 * 60 * 1000,
  });
}
