import { describe, it, expect, vi, beforeEach } from 'vitest';
import { authService } from '../authService';
import api from '../api';
import type { LoginResponse, RefreshTokenResponse, User } from '../../types/auth';

vi.mock('../api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

const mockUser: User = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'Administrator',
  is_active: true,
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
};

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('login', () => {
    it('calls POST /auth/login with credentials', async () => {
      const loginResponse: LoginResponse = {
        access_token: 'access-tok',
        refresh_token: 'refresh-tok',
        token_type: 'bearer',
        expires_in: 3600,
        user: mockUser,
      };
      vi.mocked(api.post).mockResolvedValueOnce({ data: loginResponse });

      const result = await authService.login({ username: 'u', password: 'p' });

      expect(api.post).toHaveBeenCalledWith('/auth/login', { username: 'u', password: 'p' });
      expect(result).toEqual(loginResponse);
    });
  });

  describe('logout', () => {
    it('calls POST /auth/logout', async () => {
      vi.mocked(api.post).mockResolvedValueOnce({ data: null });
      await authService.logout();
      expect(api.post).toHaveBeenCalledWith('/auth/logout');
    });
  });

  describe('getCurrentUser', () => {
    it('calls GET /auth/me and returns user', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockUser });
      const result = await authService.getCurrentUser();
      expect(api.get).toHaveBeenCalledWith('/auth/me');
      expect(result).toEqual(mockUser);
    });
  });

  describe('refreshToken', () => {
    it('calls POST /auth/refresh and returns new token data', async () => {
      const refreshResponse: RefreshTokenResponse = {
        access_token: 'new-access',
        token_type: 'bearer',
        expires_in: 3600,
      };
      vi.mocked(api.post).mockResolvedValueOnce({ data: refreshResponse });
      const result = await authService.refreshToken();
      expect(api.post).toHaveBeenCalledWith('/auth/refresh');
      expect(result).toEqual(refreshResponse);
    });
  });
});
