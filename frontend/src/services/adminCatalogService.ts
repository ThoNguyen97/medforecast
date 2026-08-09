import api from './api';

export interface DiseaseItem {
  key: string;
  label: string;
  description?: string | null;
}

export interface RegionItem {
  name: string;
  province?: string | null;
  description?: string | null;
}

export const adminCatalogService = {
  // ── Diseases ──────────────────────────────────────────────────────────
  async listDiseases(): Promise<DiseaseItem[]> {
    const res = await api.get<DiseaseItem[]>('/admin/diseases');
    return res.data;
  },
  async createDisease(payload: DiseaseItem): Promise<DiseaseItem> {
    const res = await api.post<DiseaseItem>('/admin/diseases', payload);
    return res.data;
  },
  async updateDisease(key: string, payload: DiseaseItem): Promise<DiseaseItem> {
    const res = await api.put<DiseaseItem>(`/admin/diseases/${encodeURIComponent(key)}`, payload);
    return res.data;
  },
  async deleteDisease(key: string): Promise<void> {
    await api.delete(`/admin/diseases/${encodeURIComponent(key)}`);
  },

  // ── Regions ───────────────────────────────────────────────────────────
  async listRegions(): Promise<RegionItem[]> {
    const res = await api.get<RegionItem[]>('/admin/regions');
    return res.data;
  },
  async createRegion(payload: RegionItem): Promise<RegionItem> {
    const res = await api.post<RegionItem>('/admin/regions', payload);
    return res.data;
  },
  async deleteRegion(name: string): Promise<void> {
    await api.delete(`/admin/regions/${encodeURIComponent(name)}`);
  },

  // ── Safety rate ───────────────────────────────────────────────────────
  async getSafetyRate(): Promise<number> {
    const res = await api.get<{ safety_rate: number }>('/admin/safety-rate');
    return res.data.safety_rate;
  },
  async updateSafetyRate(rate: number): Promise<number> {
    const res = await api.put<{ safety_rate: number }>('/admin/safety-rate', {
      safety_rate: rate,
    });
    return res.data.safety_rate;
  },
};
