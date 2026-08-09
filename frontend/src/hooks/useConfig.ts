import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { configService } from '../services/configService';
import type {
  ConfigUpdateRequest,
  ConversionRatiosUpdateRequest,
  ThresholdsUpdateRequest,
} from '../types/config';

// ─── Query Keys ──────────────────────────────────────────────────────────────

const CONFIG_KEYS = {
  all: ['config'] as const,
  single: (key: string) => ['config', key] as const,
  conversionRatios: ['config', 'conversion-ratios'] as const,
  thresholds: ['config', 'thresholds'] as const,
  auditLogs: (params?: object) => ['audit-logs', params] as const,
};

// ─── Queries ─────────────────────────────────────────────────────────────────

/** Fetch all system configuration entries */
export function useConfigs() {
  return useQuery({
    queryKey: CONFIG_KEYS.all,
    queryFn: () => configService.getConfigs(),
  });
}

/** Fetch a single config entry by key */
export function useConfigByKey(key: string) {
  return useQuery({
    queryKey: CONFIG_KEYS.single(key),
    queryFn: () => configService.getConfigByKey(key),
    enabled: !!key,
  });
}

/** Fetch all conversion ratios */
export function useConversionRatios() {
  return useQuery({
    queryKey: CONFIG_KEYS.conversionRatios,
    queryFn: () => configService.getConversionRatios(),
  });
}

/** Fetch shortage thresholds */
export function useThresholds() {
  return useQuery({
    queryKey: CONFIG_KEYS.thresholds,
    queryFn: () => configService.getThresholds(),
  });
}

/** Fetch audit logs for configuration change history */
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

/** Update a single configuration key */
export function useUpdateConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ key, data }: { key: string; data: ConfigUpdateRequest }) =>
      configService.updateConfig(key, data),
    onSuccess: (_result, { key }) => {
      queryClient.invalidateQueries({ queryKey: CONFIG_KEYS.all });
      queryClient.invalidateQueries({ queryKey: CONFIG_KEYS.single(key) });
      // Invalidate audit logs so the change history refreshes
      queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
    },
  });
}

/** Update conversion ratios */
export function useUpdateConversionRatios() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ConversionRatiosUpdateRequest) =>
      configService.updateConversionRatios(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_KEYS.conversionRatios });
      queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
    },
  });
}

/** Update shortage thresholds */
export function useUpdateThresholds() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ThresholdsUpdateRequest) =>
      configService.updateThresholds(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CONFIG_KEYS.thresholds });
      queryClient.invalidateQueries({ queryKey: ['audit-logs'] });
    },
  });
}
