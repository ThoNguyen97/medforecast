import api from './api';

export interface HierForecast {
  block: string;
  region: string;
  target_period: string;
  method: string;
  group_forecast: number;
  group_interval: { lower: number; upper: number };
  by_code: Record<string, number>;
  by_code_upper: Record<string, number>;
  weather_used: boolean;
  n_history_months: number;
}

export const forecastHierService = {
  async blocks(): Promise<string[]> {
    const r = await api.get<{ blocks: string[] }>('/forecast-hier/blocks');
    return r.data.blocks;
  },
  async methods(): Promise<string[]> {
    const r = await api.get<{ methods: string[] }>('/forecast-hier/methods');
    return r.data.methods;
  },
  async forecast(block: string, method = 'top_down_dynamic'): Promise<HierForecast> {
    const r = await api.get<HierForecast>(`/forecast-hier/${encodeURIComponent(block)}`, {
      params: { method },
    });
    return r.data;
  },
};
