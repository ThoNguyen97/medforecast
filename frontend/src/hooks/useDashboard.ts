import { useQuery } from '@tanstack/react-query';
import { useRef } from 'react';
import { dashboardService } from '../services/dashboardService';
import { DASHBOARD_REFRESH_INTERVAL_MS } from '../utils/constants';
import { useAuthStore } from '../store/authStore';

export function useDashboardSummary() {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => dashboardService.getSummary(),
    refetchInterval: isAuthenticated ? DASHBOARD_REFRESH_INTERVAL_MS : false,
    staleTime: DASHBOARD_REFRESH_INTERVAL_MS,
    enabled: isAuthenticated,
    retry: false,
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
  });
}

export function useCaseTrend(months = 6) {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['dashboard', 'case-trend', months],
    queryFn: () => dashboardService.getCaseTrend(months),
    refetchInterval: isAuthenticated ? DASHBOARD_REFRESH_INTERVAL_MS : false,
    staleTime: DASHBOARD_REFRESH_INTERVAL_MS,
    enabled: isAuthenticated,
    retry: false,
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
  });
}

export function useDemandVsStock(topN = 5) {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['dashboard', 'demand-vs-stock', topN],
    queryFn: () => dashboardService.getDemandVsStock(topN),
    refetchInterval: isAuthenticated ? DASHBOARD_REFRESH_INTERVAL_MS : false,
    staleTime: DASHBOARD_REFRESH_INTERVAL_MS,
    enabled: isAuthenticated,
    retry: false,
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
  });
}

export function useDashboardCriticalAlerts(limit = 5) {
  const { isAuthenticated } = useAuthStore();
  // Lần fetch đầu (mount/auto) dùng cache; các lần refetch thủ công sẽ
  // bỏ qua cache để lấy số liệu tồn kho real-time.
  const manualRefresh = useRef(false);
  const query = useQuery({
    queryKey: ['dashboard', 'critical-alerts', limit],
    queryFn: async () => {
      const useRefresh = manualRefresh.current;
      manualRefresh.current = false;
      return dashboardService.getCriticalAlerts(limit, useRefresh);
    },
    refetchInterval: isAuthenticated ? DASHBOARD_REFRESH_INTERVAL_MS : false,
    staleTime: DASHBOARD_REFRESH_INTERVAL_MS,
    enabled: isAuthenticated,
    retry: false,
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
  });

  // refetch() bọc lại để đánh dấu lần gọi tiếp theo là refresh thủ công
  const refetch = (...args: Parameters<typeof query.refetch>) => {
    manualRefresh.current = true;
    return query.refetch(...args);
  };

  return { ...query, refetch };
}
