import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import type { DashboardV2, DashboardV2Params } from '../types/dashboardV2';
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

// ── Dashboard v2 (Tuần 3) ────────────────────────────────────────────────────

/** Payload nhanh: KPI, DOI, bảng cảnh báo, phân cấp, chất lượng, tình trạng dữ liệu. */
export function useDashboardV2(params: DashboardV2Params) {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['dashboard', 'v2', params.focus, params.level ?? 'all', params.limit ?? 8],
    queryFn: () => dashboardService.getV2(params),
    refetchInterval: isAuthenticated ? DASHBOARD_REFRESH_INTERVAL_MS : false,
    staleTime: 60_000,
    enabled: isAuthenticated,
    retry: false,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev, // đổi bộ lọc không nháy trắng
  });
}

/**
 * Dự báo ba khối. Khi dự báo vừa sẵn sàng, làm mới payload v2 để bảng cảnh
 * báo có cột "Thiếu hụt dự kiến" (Tầng 2 chỉ chạy khi Tầng 1 đã có).
 */
export function useDashboardForecast() {
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['dashboard', 'v2-forecast'],
    queryFn: () => dashboardService.getV2Forecast(),
    staleTime: DASHBOARD_REFRESH_INTERVAL_MS,
    enabled: isAuthenticated,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const computedAt = query.data?.computed_at ?? null;
  useEffect(() => {
    if (!computedAt) return;
    // Chỉ làm mới khi payload v2 đang thiếu dự báo — tránh gọi thừa lúc mount.
    const thieu = queryClient
      .getQueriesData<DashboardV2>({ queryKey: ['dashboard', 'v2'] })
      .some(([, d]) => d && (!d.forecast.ready || !d.demand.ready));
    if (thieu) queryClient.invalidateQueries({ queryKey: ['dashboard', 'v2'] });
  }, [computedAt, queryClient]);
  return query;
}
