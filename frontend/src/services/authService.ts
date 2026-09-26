import api from './api';
import type { LoginRequest, LoginResponse, RefreshTokenResponse, User } from '../types/auth';

/** Gọi API xác thực (/auth). */
class AuthService {
  /** Đăng nhập bằng tên đăng nhập/mật khẩu. */
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await api.post<LoginResponse>('/auth/login', credentials);
    return response.data;
  }

  /** Đăng xuất phiên hiện tại. */
  async logout(): Promise<void> {
    await api.post('/auth/logout');
  }

  /** Thông tin người dùng đang đăng nhập. */
  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/me');
    return response.data;
  }

  /** Làm mới access token. */
  async refreshToken(): Promise<RefreshTokenResponse> {
    const response = await api.post<RefreshTokenResponse>('/auth/refresh');
    return response.data;
  }
}

export const authService = new AuthService();
