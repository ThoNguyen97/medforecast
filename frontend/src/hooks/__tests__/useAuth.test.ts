import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAuth } from '../useAuth';
import { authService } from '../../services/authService';
import { useAuthStore } from '../../store/authStore';
import type { User, LoginResponse } from '../../types/auth';

vi.mock('../../services/authService');

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Provide MemoryRouter context for the hook
import { createElement, type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';

function makeWrapper() {
  return ({ children }: { children: ReactNode }) =>
    createElement(MemoryRouter, {}, children);
}

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

const loginResponse: LoginResponse = {
  access_token: 'access-tok',
  refresh_token: 'refresh-tok',
  token_type: 'bearer',
  expires_in: 3600,
  user: mockUser,
};

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      tokenExpiry: null,
    });
    localStorage.clear();
  });

  it('returns current user and isAuthenticated', () => {
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('login succeeds and sets auth', async () => {
    vi.mocked(authService.login).mockResolvedValueOnce(loginResponse);
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    let loginResult: any;
    await act(async () => {
      loginResult = await result.current.login({ username: 'admin', password: 'pass' });
    });

    expect(loginResult.success).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('login returns error on failure', async () => {
    vi.mocked(authService.login).mockRejectedValueOnce(new Error('Invalid credentials'));
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    let loginResult: any;
    await act(async () => {
      loginResult = await result.current.login({ username: 'admin', password: 'wrong' });
    });

    expect(loginResult.success).toBe(false);
    expect(loginResult.error).toBe('Invalid credentials');
  });

  it('logout clears auth and navigates to login', async () => {
    useAuthStore.setState({ user: mockUser, isAuthenticated: true, token: 'tok' });
    vi.mocked(authService.logout).mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.logout();
    });

    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(mockNavigate).toHaveBeenCalled();
  });

  it('logout works even if API call fails', async () => {
    useAuthStore.setState({ user: mockUser, isAuthenticated: true, token: 'tok' });
    vi.mocked(authService.logout).mockRejectedValueOnce(new Error('Network error'));
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.logout();
    });

    // Still clears auth despite API error
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('refreshToken updates auth token', async () => {
    useAuthStore.setState({ user: mockUser, isAuthenticated: true, token: 'old-tok' });
    vi.mocked(authService.refreshToken).mockResolvedValueOnce({
      access_token: 'new-tok',
      token_type: 'bearer',
      expires_in: 3600,
    });
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    let refreshResult: any;
    await act(async () => {
      refreshResult = await result.current.refreshToken();
    });

    expect(refreshResult.success).toBe(true);
    expect(useAuthStore.getState().token).toBe('new-tok');
  });

  it('checkAndRefreshToken refreshes when token is expired', async () => {
    // Set expired token
    useAuthStore.setState({
      user: mockUser,
      isAuthenticated: true,
      token: 'expired-tok',
      tokenExpiry: Date.now() - 1000, // already expired
    });
    vi.mocked(authService.refreshToken).mockResolvedValueOnce({
      access_token: 'refreshed-tok',
      token_type: 'bearer',
      expires_in: 3600,
    });
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.checkAndRefreshToken();
    });

    expect(authService.refreshToken).toHaveBeenCalledTimes(1);
  });
});
