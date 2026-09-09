import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertsService } from '../services/alertsService';

export function useAlerts(params?: {
  skip?: number;
  limit?: number;
  severity?: string;
  is_resolved?: boolean;
}) {
  return useQuery({
    queryKey: ['alerts', params],
    queryFn: () => alertsService.getAlerts(params),
  });
}

export function useActiveAlerts(params?: {
  skip?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ['alerts', 'active', params],
    queryFn: () => alertsService.getActiveAlerts(params),
  });
}

export function useAlertById(id: number) {
  return useQuery({
    queryKey: ['alerts', id],
    queryFn: () => alertsService.getAlertById(id),
    enabled: !!id,
  });
}

export function useCriticalAlerts(params?: {
  skip?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ['alerts', 'critical', params],
    queryFn: () => alertsService.getCriticalAlerts(params),
  });
}

export function useResolveAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => alertsService.resolveAlert(id),
    onSuccess: () => {
      // Invalidate and refetch all alert-related queries
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
}

export function useFulfillAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => alertsService.fulfillAlert(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });
}
