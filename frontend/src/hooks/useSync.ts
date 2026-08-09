import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { syncService } from '../services/syncService';
import { useAuthStore } from '../store/authStore';

/** Trạng thái đồng bộ gần nhất (đồng bộ lần cuối, số ca, số tồn kho). */
export function useSyncStatus() {
  const { isAuthenticated } = useAuthStore();
  return useQuery({
    queryKey: ['sync', 'status'],
    queryFn: () => syncService.getStatus(),
    enabled: isAuthenticated,
    staleTime: 30_000,
    retry: false,
  });
}

/** Chạy đồng bộ dữ liệu từ HIS; sau khi xong, làm mới dashboard. */
export function useRunSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (full = false) => syncService.run(full),
    onSuccess: () => {
      // dữ liệu vừa cập nhật → làm mới dashboard, tồn kho, dự báo, trạng thái
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['sync'] });
    },
  });
}
