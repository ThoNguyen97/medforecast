import api from './api';
import type {
  DiseaseCase,
  DiseaseCaseCreate,
  DiseaseStatsResponse,
  DiseaseTrendsResponse,
  DiseaseType,
} from '../types/epidemiology';

export const epidemiologyService = {
  /**
   * Get all disease case records with optional filters
   */
  async getDiseaseCases(params?: {
    skip?: number;
    limit?: number;
    disease_type?: DiseaseType;
    location?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<DiseaseCase[]> {
    // Trailing slash bắt buộc — nếu thiếu, backend trả 307 redirect và một số
    // môi trường (proxy/CORS) làm rớt query params hoặc Authorization header.
    const response = await api.get<DiseaseCase[]>('/disease-cases/', { params });
    return response.data;
  },

  /**
   * Create a new disease case record
   */
  async createDiseaseCase(data: DiseaseCaseCreate): Promise<DiseaseCase> {
    const response = await api.post<DiseaseCase>('/disease-cases', data);
    return response.data;
  },

  /**
   * Get disease case statistics grouped by disease type
   */
  async getStatistics(params?: {
    location?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<DiseaseStatsResponse> {
    const response = await api.get<DiseaseStatsResponse>('/disease-cases/stats', {
      params,
    });
    return response.data;
  },

  /**
   * Get disease case trend data (time series)
   */
  async getTrends(params?: {
    disease_type?: DiseaseType;
    location?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
  }): Promise<DiseaseTrendsResponse> {
    const response = await api.get<DiseaseTrendsResponse>('/disease-cases/trends', {
      params,
    });
    return response.data;
  },
};
