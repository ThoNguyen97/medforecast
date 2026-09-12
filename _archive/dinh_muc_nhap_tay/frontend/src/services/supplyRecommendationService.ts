import api from './api';

export interface SeverityBreakdown {
  mild_rate: number;
  moderate_rate: number;
  severe_rate: number;
  mild_cases: number;
  moderate_cases: number;
  severe_cases: number;
}

export interface RecommendationItem {
  supply_id: number;
  supply_code: string;
  drug_code: string;
  ten_hoat_chat: string;
  unit: string;
  group_name: string;
  norm_mild: number;
  norm_moderate: number;
  norm_severe: number;
  need_before_buffer: number;
  buffer_rate: number;
  predicted_need: number;
  current_stock: number;
  safety_stock: number;
  suggested_import: number;
  status: 'shortage' | 'sufficient';
}

export interface DiseaseRecommendation {
  icd_code: string;
  disease_name: string;
  forecast_month: string;
  predicted_cases: number;
  severity_breakdown: SeverityBreakdown;
  buffer_rate: number;
  total_supplies: number;
  total_suggested_import_value: number;
  items: RecommendationItem[];
}

export interface AggregatedItem {
  supply_id: number;
  supply_code: string;
  drug_code: string;
  ten_hoat_chat: string;
  unit: string;
  group_name: string;
  current_stock: number;
  safety_stock: number;
  buffer_rate: number;
  need_before_buffer_total: number;
  predicted_need_total: number;
  suggested_import: number;
  status: 'shortage' | 'sufficient';
  by_disease: Array<{
    icd_code: string;
    disease_name: string;
    predicted_cases: number;
    predicted_need: number;
  }>;
}

export interface MonthRecommendation {
  forecast_month: string;
  location: string | null;
  buffer_rate: number;
  diseases: DiseaseRecommendation[];
  total_supplies: number;
  items: AggregatedItem[];
}

export const supplyRecommendationService = {
  async calculateForDisease(payload: {
    icd_code: string;
    predicted_cases: number;
    forecast_month: string;
    buffer_rate?: number;
    save?: boolean;
  }): Promise<DiseaseRecommendation> {
    const res = await api.post<DiseaseRecommendation>(
      '/supply-recommendations/calculate',
      payload,
    );
    return res.data;
  },

  async calculateForMonth(payload: {
    forecast_month: string;
    location?: string | null;
    buffer_rate?: number;
    save?: boolean;
  }): Promise<MonthRecommendation> {
    const res = await api.post<MonthRecommendation>(
      '/supply-recommendations/calculate-month',
      payload,
    );
    return res.data;
  },
};
