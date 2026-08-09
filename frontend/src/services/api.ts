import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL, TOKEN_KEY, REFRESH_TOKEN_KEY, TOKEN_EXPIRY_KEY } from '../utils/constants';
import { useAuthStore } from '../store/authStore';

// Flag to prevent multiple redirects
let isLoggingOut = false;

// Create Axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
});

// Request interceptor — inject auth token
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

// Response interceptor — handle 401
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  async (error) => {
    if (isLoggingOut) {
      return Promise.reject(new Error('Session expired'));
    }

    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // Handle 401 Unauthorized
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const token = localStorage.getItem(TOKEN_KEY);
      if (token) {
        try {
          const response = await axios.post(
            `${API_BASE_URL}/auth/refresh`,
            {},
            {
              headers: { Authorization: `Bearer ${token}` },
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
          // Refresh failed — logout
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

  // Clear storage
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);

  // Update zustand store
  useAuthStore.getState().logout();

  // Redirect
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }

  // Reset after redirect
  setTimeout(() => { isLoggingOut = false; }, 2000);
}

export default api;
