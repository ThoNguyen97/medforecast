import api from './api';

export interface SeverityRate {
  id: number;
  icd_code: string;
  disease_name: string;
  mild_rate: number;
  moderate_rate: number;
  severe_rate: number;
  note: string | null;
}

export interface SupplyNormCell {
  supply_id: number;
  supply_code: string;
  drug_code: string;
  ten_hoat_chat: string;
  unit: string;
  group_name: string;
  mild: number;
  moderate: number;
  severe: number;
}

export interface NormMatrix {
  icd_code: string;
  disease_name: string;
  supplies: SupplyNormCell[];
}

export interface NormUpsert {
  icd_code: string;
  severity: 'mild' | 'moderate' | 'severe';
  supply_id: number;
  quantity_per_case: number;
}

export const adminSeverityService = {
  async listSeverityRates(): Promise<SeverityRate[]> {
    const res = await api.get<SeverityRate[]>('/admin/severity-rates');
    return res.data;
  },

  async updateSeverityRate(
    icd_code: string,
    payload: {
      mild_rate: number;
      moderate_rate: number;
      severe_rate: number;
      note?: string;
    },
  ): Promise<SeverityRate> {
    const res = await api.put<SeverityRate>(
      `/admin/severity-rates/${icd_code}`,
      payload,
    );
    return res.data;
  },

  async getNormMatrix(icd_code: string): Promise<NormMatrix> {
    const res = await api.get<NormMatrix>('/admin/supply-norms/matrix', {
      params: { icd_code },
    });
    return res.data;
  },

  async upsertNorm(payload: NormUpsert): Promise<any> {
    const res = await api.put('/admin/supply-norms', payload);
    return res.data;
  },

  async bulkUpsertNorms(norms: NormUpsert[]): Promise<{
    created: number;
    updated: number;
    errors: Array<{ idx: number; reason: string }>;
  }> {
    const res = await api.put('/admin/supply-norms/bulk', { norms });
    return res.data;
  },
};
