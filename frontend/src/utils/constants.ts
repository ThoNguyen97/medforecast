// Đường dẫn tương đối: dev đi qua Vite proxy, production đi qua nginx (location /api/) —
// không phụ thuộc host, tránh lỗi CORS/Network Error khi deploy.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const TOKEN_KEY = 'medforecast_token';
export const REFRESH_TOKEN_KEY = 'medforecast_refresh_token';
export const USER_KEY = 'medforecast_user';
export const TOKEN_EXPIRY_KEY = 'medforecast_token_expiry';

export const DASHBOARD_REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 phút

// Danh mục thuốc: 8 nhãn tính bên PROD (#DrugMeta trong usp_MedForecast_DayDuLieu),
// đồng bộ nguyên văn vào medical_supplies.category. Khoá = nhãn; hai khoá kỹ thuật
// medicine/other dành cho dữ liệu nhập tay.
export const SUPPLY_CATEGORY_LABELS: Record<string, string> = {
  'Kháng sinh': 'Kháng sinh',
  'Thuốc hạ sốt giảm đau': 'Thuốc hạ sốt giảm đau',
  'Thuốc long đờm': 'Thuốc long đờm',
  'Thuốc giãn phế quản': 'Thuốc giãn phế quản',
  'Corticoid': 'Corticoid',
  'Kháng histamin': 'Kháng histamin',
  'Dịch truyền': 'Dịch truyền',
  'Khác': 'Khác',
  medicine: 'Thuốc',
  other: 'Khác',
};

export const USER_ROLE_LABELS: Record<string, string> = {
  Administrator: 'Quản trị viên',
  Pharmacist: 'Dược sĩ',
  Inventory_Manager: 'Quản lý kho',
};

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  INVENTORY: '/inventory',
  FORECASTING: '/forecasting',
  ALERTS: '/alerts',
  EPIDEMIOLOGY: '/epidemiology',
  WEATHER: '/weather',
  REPORTS: '/reports',
  SETTINGS: '/settings',
} as const;

export const APP_NAME = 'MedForecast AI';
export const APP_DESCRIPTION = 'Hệ thống Dự báo Nhu cầu Thuốc';
