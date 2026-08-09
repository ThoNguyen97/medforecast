import api from './api';

export interface SupplyRequirementSummaryItem {
  supply_id: number;
  supply_name: string;
  supply_category?: string | null;
  supply_unit?: string | null;
  total_required_quantity: number;
  current_stock?: number | null;
  shortage_amount?: number | null;
  disease_types: string[];
  requirement_count: number;
}

export interface SupplyRequirementSummaryResponse {
  total_supplies: number;
  supplies_with_shortage: number;
  items: SupplyRequirementSummaryItem[];
}

export const supplyRequirementsService = {
  async getSummary(params?: {
    disease_type?: string;
    category?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<SupplyRequirementSummaryResponse> {
    const res = await api.get<SupplyRequirementSummaryResponse>(
      '/supply-requirements/summary',
      { params },
    );
    return res.data;
  },
};
