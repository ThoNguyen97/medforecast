import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configService } from '../services/configService';
import type { ConfigUpdateRequest } from '../types/config';

// ─── Query Keys ──────────────────────────────────────────────────────────────

const CONFIG_KEYS = {
  all: ['config'] as const,
  single: (key: string) => ['config', key] as const,
  auditLogs: (params?: object) => ['audit-logs', params] as const,
};

// ─── Queries ─────────────────────────────────────────────────────────────────

export function useConfigs() {
  return useQuery({
    queryKey: CONFIG_KEYS.all,
    queryFn: () => configService.getConfigs(),
  });
}

export function useConfigByKey(key: string) {
  return useQuery({
    queryKey: CONFIG_KEYS.single(key),
    queryFn: () => configService.getConfigByKey(key),
    enabled: !!key,
  });
}

export function useAuditLogs(params?: {
  skip?: number;
  limit?: number;
  table_name?: string;
  action?: string;
  user_id?: number;
  start_date?: string;
  end_date?: string;
}) {
  return useQuery({
    queryKey: CONFIG_KEYS.auditLogs(params),
    queryFn: () => configService.getAuditLogs(params),
  });
}

// ─── Mutations ────────────────────────────────────────────────────────────────

export function useUpdateConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ key, data }: { key: string; data: ConfigUpdateRequest }) =>
      configService.updateConfig(key, data),
    onSuccess: (_result, { key }) => {
      queryClient.invalidateQueries({ queryKey: CONFIG_KEYS.all });
      queryClient.invalidateQueries({ queryKey: CONFIG_KEYS.single(key) });
      // Làm mới audit log
      queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
    },
  });
}
