import api from './api';

export interface DiseaseItem {
  key: string;
  label: string;
  description?: string | null;
}

export interface DiseaseGroupItem {
  key: string;
  name: string;
  /** Danh sách mã bệnh (key trong Danh mục bệnh) thuộc nhóm này. */
  icd_codes: string[];
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

  // ── Disease groups ────────────────────────────────────────────────────
  async listDiseaseGroups(): Promise<DiseaseGroupItem[]> {
    const res = await api.get<DiseaseGroupItem[]>('/admin/disease-groups');
    return res.data;
  },
  async createDiseaseGroup(payload: DiseaseGroupItem): Promise<DiseaseGroupItem> {
    const res = await api.post<DiseaseGroupItem>('/admin/disease-groups', payload);
    return res.data;
  },
  async updateDiseaseGroup(key: string, payload: DiseaseGroupItem): Promise<DiseaseGroupItem> {
    const res = await api.put<DiseaseGroupItem>(`/admin/disease-groups/${encodeURIComponent(key)}`, payload);
    return res.data;
  },
  async deleteDiseaseGroup(key: string): Promise<void> {
    await api.delete(`/admin/disease-groups/${encodeURIComponent(key)}`);
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
};
