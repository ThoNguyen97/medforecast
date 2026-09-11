import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import type { DashboardV2, DashboardV2Params } from '../types/dashboardV2';
import { dashboardService } from '../services/dashboardService';
import { DASHBOARD_REFRESH_INTERVAL_MS } from '../utils/constants';
import { useAuthStore } from '../store/authStore';

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
