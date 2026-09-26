// Mã ICD hô hấp dùng để dự báo
export type DiseaseType = 'J20' | 'J06' | 'J02' | 'J01';

export interface DiseaseCase {
  id: number;
  recorded_at: string;
  icd_code: DiseaseType | string;
  disease_name: string;
  // luôn 'respiratory', giữ để tương thích API
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

// Mã ICD → tên bệnh tiếng Việt
export const DISEASE_TYPE_LABELS: Record<string, string> = {
  J20: 'Viêm phế quản cấp',
  J06: 'Nhiễm trùng đường hô hấp trên cấp',
  J02: 'Viêm họng cấp',
  J01: 'Viêm xoang cấp',
  respiratory: 'Bệnh hô hấp',
};

