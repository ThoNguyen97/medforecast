// 4 bệnh hô hấp đơn giản dùng để dự báo
export type DiseaseType = 'J20' | 'J06' | 'J02' | 'J01';

export interface DiseaseCase {
  id: number;
  recorded_at: string;
  icd_code: DiseaseType | string;
  disease_name: string;
  // disease_type giữ lại để tương thích code cũ — nay luôn là 'respiratory'
  disease_type?: string;
  case_count: number;
  location: string;
  district_ward?: string | null;
  severity?: string;
  length_of_stay?: number | null;
  sub_icd_count?: number | null;
  data_source?: string;
  note?: string | null;
  created_by?: string | null;
  created_at: string;
}

export interface DiseaseCaseCreate {
  recorded_at: string;
  icd_code: DiseaseType | string;
  disease_name: string;
  disease_type?: string;
  case_count: number;
  location: string;
  district_ward?: string | null;
  severity?: string;
  length_of_stay?: number;
  sub_icd_count?: number;
  data_source?: string;
  note?: string;
}

export interface DiseaseStatistic {
  icd_code: DiseaseType | string;
  disease_name: string;
  total_cases: number;
  record_count: number;
  latest_record_date: string;
  avg_cases_per_day?: number;
}

export interface DiseaseTrendPoint {
  date: string;
  case_count: number;
  icd_code: DiseaseType | string;
  disease_name: string;
}

export interface DiseaseStatsResponse {
  statistics: DiseaseStatistic[];
  filters: {
    location?: string;
    start_date?: string;
    end_date?: string;
  };
}

export interface DiseaseTrendsResponse {
  trends: DiseaseTrendPoint[];
  filters: {
    icd_code?: DiseaseType;
    location?: string;
    start_date?: string;
    end_date?: string;
  };
}

// Map mã ICD → tên bệnh tiếng Việt
export const DISEASE_TYPE_LABELS: Record<string, string> = {
  J20: 'Viêm phế quản cấp',
  J06: 'Nhiễm trùng đường hô hấp trên cấp',
  J02: 'Viêm họng cấp',
  J01: 'Viêm xoang cấp',
  // Giữ lại các nhãn cũ để tương thích nếu DB còn dữ liệu cũ
  respiratory: 'Bệnh hô hấp',
};

// Màu sắc cho từng bệnh
// Palette categorical đã validate (dataviz): gán theo thứ tự mã cố định, không dùng
// đỏ trạng thái cho series. Đỏ chỉ dành cho cảnh báo.
export const DISEASE_TYPE_COLORS: Record<string, string> = {
  J01: '#2a78d6', // slot 1 blue    — viêm xoang cấp
  J02: '#008300', // slot 2 green   — viêm họng cấp
  J06: '#e87ba4', // slot 3 magenta — nhiễm trùng hô hấp trên
  J20: '#eda100', // slot 4 yellow  — viêm phế quản cấp
  respiratory: '#6b7280',
};
