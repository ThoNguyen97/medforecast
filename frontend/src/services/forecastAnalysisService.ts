import api from './api';

interface DiseaseOption {
  key: string;
  label: string;
}

export interface AnalyzeRequest {
  disease_type: string;
  region?: string | null;
  target_month: number;
  target_year: number;
  /** true = ghi nhận kết quả vào DB (nút "Ghi nhận dự báo"). */
  save?: boolean;
  /** Chỉ dùng khi save=true: cho phép ghi đè bản đã ghi nhận của cùng khóa. */
  overwrite?: boolean;
}

export interface AnalyzeResponse {
  /** false = chưa ghi nhận dự báo nào cho khóa này (chỉ có ở POST /forecast/saved). */
  found?: boolean;
  /** true = kỳ này đã có bản ghi nhận, cần người dùng xác nhận ghi đè. */
  conflict?: boolean;
  message?: string;
  existing?: {
    forecast_id: number;
    predicted_cases: number;
    recorded_at: string | null;
    created_by: string | null;
  };
  forecast: {
    /** null khi mới phân tích mà chưa bấm "Ghi nhận dự báo". */
    id: number | null;
    predicted_cases: number;
    baseline: number;
    increase_pct: number;
    risk_level: 'low' | 'medium' | 'high' | 'very_high';
    risk_label: string;
    weather_factor: number;
    trend_factor: number;
    disease_type: string;
    disease_label: string;
    region: string;
    target_month: number;
    target_year: number;
    /** Kết quả này đã được ghi nhận vào DB hay mới chỉ là bản xem trước. */
    is_recorded?: boolean;
    /** Thời điểm ghi nhận (ISO) — null khi chưa ghi nhận. */
    recorded_at?: string | null;
    /** Lý do backend từ chối ghi nhận khi khoá không có căn cứ dự báo
     *  (chuỗi quá ngắn, không có ca cùng kỳ). */
    khong_ghi_nhan?: string | null;
  };
  explanation_bullets: string[];
  /** Backtest nhanh N bước cuối: rmse/r2 không đo → null. */
  accuracy?: {
    mae: number | null;
    rmse: number | null;
    mape: number | null;
    r2: number | null;
    n_samples: number;
    accuracy_pct?: number | null;
  } | null;
  weather: {
    forecast: Record<string, number | null>;
    history_avg: Record<string, number | null>;
  };
  charts: {
    main: Array<Record<string, any>>;
    comparison: Array<{ year: number; value: number; is_forecast: boolean }>;
    trend_current_year: Array<{ month: string; value: number }>;
    correlation: Array<{
      year: number;
      cases: number;
      temp: number | null;
      humidity: number | null;
      rainfall: number | null;
      aqi: number | null;
      pm25: number | null;
      is_forecast: boolean;
    }>;
    correlation_coefficients?: {
      temp: number | null;
      humidity: number | null;
      rainfall: number | null;
      aqi: number | null;
      pm25: number | null;
    };
    years: number[];
  };
}

export interface ForecastHistoryItem {
  id: number;
  month: string;
  disease_type: string;
  disease_label: string;
  region: string;
  predicted_cases: number;
  actual_cases: number | null;
  deviation_pct: number | null;
  risk_level: string | null;
  created_at: string | null;
  /** Tài khoản đã ghi nhận dự báo này. */
  created_by: string | null;
  /** true = bản Toàn quốc (location = NULL) — số chính thức nuôi Tổng quan/Cảnh báo;
   *  các bản theo tỉnh chỉ tham khảo, không cộng lại thành Toàn quốc. */
  is_nationwide?: boolean;
}

export const forecastAnalysisService = {
  async listDiseases(): Promise<DiseaseOption[]> {
    const res = await api.get<DiseaseOption[]>('/forecast/diseases');
    return res.data;
  },

  async listRegions(): Promise<string[]> {
    const res = await api.get<string[]>('/forecast/regions');
    return res.data;
  },

  async analyze(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
    const res = await api.post<AnalyzeResponse>('/forecast/analyze', payload);
    return res.data;
  },

  /**
   * Nạp bản dự báo đã ghi nhận theo khóa (nhóm bệnh, khu vực, tháng).
   * Chỉ đọc, không chạy mô hình; trả null nếu kỳ đó chưa ghi nhận.
   */
  async loadSaved(payload: AnalyzeRequest): Promise<AnalyzeResponse | null> {
    // Truy vấn đọc: timeout ngắn hơn mặc định 60s để báo lỗi sớm khi backend
    // không phản hồi.
    const res = await api.post<AnalyzeResponse>('/forecast/saved', payload, {
      timeout: 20000,
    });
    return res.data?.found === false ? null : res.data;
  },

  async getHistory(params?: {
    limit?: number;
    disease_type?: string;
    region?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<ForecastHistoryItem[]> {
    const res = await api.get<ForecastHistoryItem[]>('/forecast/history', { params });
    return res.data;
  },

  /** Xoá một bản dự báo đã ghi nhận (chủ sở hữu hoặc Quản trị viên). */
  async deleteForecast(forecastId: number): Promise<{ deleted: number; id: number }> {
    const res = await api.delete(`/forecast/${forecastId}`);
    return res.data;
  },

  /** Xoá toàn bộ lịch sử dự báo (chỉ Quản trị viên). */
  async deleteAllForecasts(): Promise<{ deleted: number }> {
    const res = await api.delete('/forecast/history');
    return res.data;
  },

  async exportForecastPdf(forecastId: number): Promise<Blob> {
    const res = await api.post(
      `/forecast/${forecastId}/export`,
      {},
      { responseType: 'blob' },
    );
    return res.data as Blob;
  },
};
