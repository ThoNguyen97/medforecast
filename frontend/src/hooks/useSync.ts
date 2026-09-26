import { useMutation, useQueryClient } from '@tanstack/react-query';
import { syncService } from '../services/syncService';

/** Chạy ETL từ view MEDFORECAST_DW (STA) vào SQLite; xong thì làm mới các truy vấn phụ thuộc. */
export function useRunSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (full?: boolean) => syncService.run(full ?? false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
      queryClient.invalidateQueries({ queryKey: ['sync'] });
    },
  });
}
