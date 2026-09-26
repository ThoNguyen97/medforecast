import api from './api';
import type {
  DiseaseCase,
  DiseaseCaseCreate,
  DiseaseType,
} from '../types/epidemiology';

export const epidemiologyService = {
  /** Danh sách ca bệnh theo bộ lọc tuỳ chọn. */
  async getDiseaseCases(params?: {
    skip?: number;
    limit?: number;
    disease_type?: DiseaseType;
    location?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<DiseaseCase[]> {
    // Cần dấu "/" cuối: thiếu thì backend trả 307, một số proxy làm rớt query
    // params hoặc header Authorization khi theo redirect.
    const response = await api.get<DiseaseCase[]>('/disease-cases/', { params });
    return response.data;
  },

  /** Thêm một bản ghi ca bệnh. */
  async createDiseaseCase(data: DiseaseCaseCreate): Promise<DiseaseCase> {
    const response = await api.post<DiseaseCase>('/disease-cases', data);
    return response.data;
  },
};
