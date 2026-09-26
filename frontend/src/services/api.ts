import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL, TOKEN_KEY, REFRESH_TOKEN_KEY, TOKEN_EXPIRY_KEY } from '../utils/constants';
import { useAuthStore } from '../store/authStore';

// Chặn chuyển hướng /login nhiều lần khi nhiều request cùng nhận 401
let isLoggingOut = false;

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Gắn access token vào mọi request
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (isLoggingOut) {
      const controller = new AbortController();
      controller.abort();
      config.signal = controller.signal;
      return config;
    }

    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Xử lý 401: thử làm mới token rồi gửi lại request
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  async (error) => {
    if (isLoggingOut) {
      return Promise.reject(new Error('Session expired'));
    }

    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // /auth/refresh nhận refresh token, không phải access token vừa hết hạn
      const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
      if (refreshToken) {
        try {
          const response = await axios.post(
            `${API_BASE_URL}/auth/refresh`,
            {},
            {
              headers: { Authorization: `Bearer ${refreshToken}` },
              timeout: 5000,
            }
          );

          const { access_token, expires_in } = response.data;
          localStorage.setItem(TOKEN_KEY, access_token);
          const expiryTime = Date.now() + expires_in * 1000;
          localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());

          if (originalRequest.headers) {
            (originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${access_token}`;
          }
          return api(originalRequest);
        } catch {
          forceLogout();
          return Promise.reject(new Error('Session expired'));
        }
      } else {
        forceLogout();
        return Promise.reject(new Error('Session expired'));
      }
    }

    const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Đã xảy ra lỗi';
    return Promise.reject(new Error(errorMessage));
  }
);

function forceLogout() {
  if (isLoggingOut) return;
  isLoggingOut = true;

  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);

  useAuthStore.getState().logout();

  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }

  setTimeout(() => { isLoggingOut = false; }, 2000);
}

export default api;
