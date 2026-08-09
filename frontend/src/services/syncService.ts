import api from './api';

export interface SyncRunResult {
  source: string;
  since: string | null;
  max_period: string | null;
  rows_ingested: number;
  rows_rejected: number;
  inventory_rows: number;
  mode: 'full' | 'incremental';
}

export interface SyncStatus {
  last_sync: {
    source: string;
    last_period: string | null;
    rows_ingested: number;
    rows_rejected: number;
    status: string;
    run_at: string;
  } | null;
  disease_cases: number;
  inventory_items: number;
  latest_period: string | null;
  history: Array<{
    source: string;
    last_period: string | null;
    rows_ingested: number;
    status: string;
    run_at: string;
  }>;
}

export const syncService = {
  async run(full = false): Promise<SyncRunResult> {
    const response = await api.post<SyncRunResult>('/sync/run', null, {
      params: { full },
      timeout: 300000, // đồng bộ có thể lâu ở lần full đầu tiên
    });
    return response.data;
  },

  async getStatus(): Promise<SyncStatus> {
    const response = await api.get<SyncStatus>('/sync/status');
    return response.data;
  },
};
