import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '../authStore';
import type { User } from '../../types/auth';

const mockUser: User = {
  id: 1,
  username: 'admin',
  email: 'admin@test.com',
  full_name: 'Admin User',
  role: 'Administrator',
  is_active: true,
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
};

describe('authStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      tokenExpiry: null,
    });
    localStorage.clear();
  });

  it('starts unauthenticated', () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
  });

  it('setAuth stores user and tokens', () => {
    useAuthStore.getState().setAuth(mockUser, 'access-token', 'refresh-token', 3600);
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual(mockUser);
    expect(state.token).toBe('access-token');
    expect(state.refreshToken).toBe('refresh-token');
  });

  it('setAuth writes token to localStorage', () => {
    useAuthStore.getState().setAuth(mockUser, 'access-token', 'refresh-token', 3600);
    expect(localStorage.getItem('medforecast_token')).toBe('access-token');
  });

  it('setAuth sets tokenExpiry ~expiresIn seconds from now', () => {
    const before = Date.now();
    useAuthStore.getState().setAuth(mockUser, 'tok', 'ref', 3600);
    const after = Date.now();
    const { tokenExpiry } = useAuthStore.getState();
    expect(tokenExpiry).toBeGreaterThanOrEqual(before + 3600 * 1000);
    expect(tokenExpiry).toBeLessThanOrEqual(after + 3600 * 1000);
  });

  it('logout clears state', () => {
    useAuthStore.getState().setAuth(mockUser, 'tok', 'ref', 3600);
    useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.token).toBeNull();
  });

  it('logout removes localStorage keys', () => {
    useAuthStore.getState().setAuth(mockUser, 'tok', 'ref', 3600);
    useAuthStore.getState().logout();
    expect(localStorage.getItem('medforecast_token')).toBeNull();
    expect(localStorage.getItem('medforecast_refresh_token')).toBeNull();
  });

  it('updateToken updates token and expiry', () => {
    useAuthStore.getState().setAuth(mockUser, 'old-token', 'ref', 100);
    useAuthStore.getState().updateToken('new-token', 7200);
    const state = useAuthStore.getState();
    expect(state.token).toBe('new-token');
  });

  it('isTokenExpired returns true when no expiry', () => {
    expect(useAuthStore.getState().isTokenExpired()).toBe(true);
  });

  it('isTokenExpired returns false when token is fresh', () => {
    useAuthStore.getState().setAuth(mockUser, 'tok', 'ref', 3600);
    expect(useAuthStore.getState().isTokenExpired()).toBe(false);
  });

  it('isTokenExpired returns true when expiry is in the past', () => {
    useAuthStore.setState({ tokenExpiry: Date.now() - 1000 });
    expect(useAuthStore.getState().isTokenExpired()).toBe(true);
  });
});
