import { useQuery } from '@tanstack/react-query';
import type { DashboardV2Params } from '../types/dashboardV2';
import { dashboardService } from '../services/dashboardService';
import { DASHBOARD_REFRESH_INTERVAL_MS } from '../utils/constants';
import { useAuthStore } from '../store/authStore';

// ── Tổng quan (/dashboard/v2) ────────────────────────────────────────────────

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

