import api from './api';
import type {
  DiseaseCase,
  DiseaseCaseCreate,
  DiseaseType,
} from '../types/epidemiology';

export const epidemiologyService = {
  async getDiseaseCases(params?: {
    skip?: number;
    limit?: number;
    disease_type?: DiseaseType;
    location?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<DiseaseCase[]> {
    // Cần "/" cuối: thiếu thì backend trả 307 và proxy có thể rớt query/Authorization
    const response = await api.get<DiseaseCase[]>('/disease-cases/', { params });
    return response.data;
  },

  async createDiseaseCase(data: DiseaseCaseCreate): Promise<DiseaseCase> {
    const response = await api.post<DiseaseCase>('/disease-cases', data);
    return response.data;
  },
};
