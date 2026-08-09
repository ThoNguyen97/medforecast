import api from './api';
import type { LoginRequest, LoginResponse, RefreshTokenResponse, User } from '../types/auth';

/**
 * Authentication service for API calls
 */
class AuthService {
  /**
   * Login user with username and password
   */
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await api.post<LoginResponse>('/auth/login', credentials);
    return response.data;
  }

  /**
   * Logout current user
   */
  async logout(): Promise<void> {
    await api.post('/auth/logout');
  }

  /**
   * Get current user information
   */
  async getCurrentUser(): Promise<User> {
    const response = await api.get<User>('/auth/me');
    return response.data;
  }

  /**
   * Refresh access token
   */
  async refreshToken(): Promise<RefreshTokenResponse> {
    const response = await api.post<RefreshTokenResponse>('/auth/refresh');
    return response.data;
  }
}

export const authService = new AuthService();
export default authService;
