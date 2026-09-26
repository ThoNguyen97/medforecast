import api from './api';

interface SyncRunResult {
  source: string;
  since: string | null;
  max_period: string | null;
  rows_ingested: number;
  rows_rejected: number;
  inventory_rows: number;
  mode: 'full' | 'incremental';
}

/** Cấu hình kết nối CSDL MEDFORECAST_DW trên STA; server không bao giờ trả
 *  mật khẩu về client. */
export interface HisConnectionConfig {
  source: 'sqlserver';
  host: string;
  port: number;
  instance: string;
  database: string;
  /** windows = Trusted_Connection; sql = UID/PWD */
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

  async getConfig(): Promise<HisConnectionConfig> {
    const response = await api.get<HisConnectionConfig>('/sync/config');
    return response.data;
  },

  async saveConfig(data: HisConnectionInput): Promise<HisConnectionConfig> {
    const response = await api.put<HisConnectionConfig>('/sync/config', data);
    return response.data;
  },

  /** Thử kết nối với cấu hình đang nhập trên form; server không lưu cấu hình này. */
  async testConfig(data: HisConnectionInput): Promise<ConnectionTestResult> {
    const response = await api.post<ConnectionTestResult>('/sync/config/test', data, {
      timeout: 30000,
    });
    return response.data;
  },
};
