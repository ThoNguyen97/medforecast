import api from './api';

export interface SyncRunResult {
  source: string;
  since: string | null;
  max_period: string | null;
  rows_ingested: number;
  rows_rejected: number;
  inventory_rows: number;
  mode: 'full' | 'incremental';
}

export interface SyncStatus {
  last_sync: {
    source: string;
    last_period: string | null;
    rows_ingested: number;
    rows_rejected: number;
    status: string;
    run_at: string;
  } | null;
  disease_cases: number;
  inventory_items: number;
  latest_period: string | null;
  history: Array<{
    source: string;
    last_period: string | null;
    rows_ingested: number;
    status: string;
    run_at: string;
  }>;
  /** Bốn bảng fact DSS (11/09/2026): có/không, kỳ mới nhất. */
  dss_tables?: Record<string, { rows: number; latest: string | null } | null>;
  /** Nguồn ứng dụng đang đọc — chỉ tên CSDL, không có host. */
  source?: { kind: 'sqlserver' | 'file' | 'unknown'; database: string | null };
  /** Mốc chốt của snapshot MEDFORECAST_DW đọc từ MF_Watermark / MF_SyncLog. */
  sta?: {
    available: boolean;
    watermarks?: Array<{ TenLuong: string; MocDaDay: string | null; LanChayCuoi: string | null }>;
    last_pushes?: Array<{
      BatDau: string;
      KetThuc: string | null;
      TrangThai: string;
      SoDongCaBenh: number | null;
      TongSoCa: number | null;
      ThongDiep: string | null;
    }>;
    warning: string | null;
  };
}

/** Cấu hình kết nối CSDL nghiên cứu MEDFORECAST_DW (SQL Server cục bộ) —
 *  mật khẩu KHÔNG bao giờ được trả về từ server. */
export interface HisConnectionConfig {
  source: 'sqlserver';
  host: string;
  port: number;
  instance: string;
  database: string;
  /** windows = Trusted_Connection (mặc định cho SQL Server cục bộ); sql = UID/PWD */
  auth: 'windows' | 'sql';
  username: string;
  driver: string;
  trust_cert: boolean;
  sql_profile: 'sta' | 'mssql';
  lookback_months: number;
  has_password: boolean;
  da_luu_trong_db: boolean;
}

/** Dữ liệu gửi lên khi lưu/thử: thêm password (để trống = giữ mật khẩu cũ). */
export type HisConnectionInput = Omit<
  HisConnectionConfig,
  'has_password' | 'da_luu_trong_db'
> & { password?: string };

export interface ConnectionTestStep {
  name: string;
  ok: boolean;
  detail: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  steps: ConnectionTestStep[];
}

export const syncService = {
  async run(full = false): Promise<SyncRunResult> {
    const response = await api.post<SyncRunResult>('/sync/run', null, {
      params: { full },
      timeout: 300000, // đồng bộ có thể lâu ở lần full đầu tiên
    });
    return response.data;
  },

  async getStatus(): Promise<SyncStatus> {
    const response = await api.get<SyncStatus>('/sync/status');
    return response.data;
  },

  async getConfig(): Promise<HisConnectionConfig> {
    const response = await api.get<HisConnectionConfig>('/sync/config');
    return response.data;
  },

  async saveConfig(data: HisConnectionInput): Promise<HisConnectionConfig> {
    const response = await api.put<HisConnectionConfig>('/sync/config', data);
    return response.data;
  },

  /** Thử kết nối với cấu hình đang nhập trên form — server CHƯA lưu gì. */
  async testConfig(data: HisConnectionInput): Promise<ConnectionTestResult> {
    const response = await api.post<ConnectionTestResult>('/sync/config/test', data, {
      timeout: 30000,
    });
    return response.data;
  },
};
