import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { authService } from '../services/authService';
import { ROUTES } from '../utils/constants';
import type { LoginRequest } from '../types/auth';

/**
 * Custom hook for authentication operations
 * 
 * Provides login, logout, and token refresh functionality
 * with integrated state management and navigation
 */
export function useAuth() {
  const navigate = useNavigate();
  const { user, isAuthenticated, setAuth, logout: clearAuth, isTokenExpired } = useAuthStore();

  /**
   * Login user with credentials
   */
  const login = useCallback(
    async (credentials: LoginRequest) => {
      try {
        const response = await authService.login(credentials);
        const { user, access_token, refresh_token, expires_in } = response;
        
        setAuth(user, access_token, refresh_token, expires_in);
        return { success: true };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Login failed';
        return { success: false, error: message };
      }
    },
    [setAuth]
  );

  /**
   * Logout user and redirect to login page
   */
  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch (error) {
      // Ignore logout API errors, still clear local state
      console.error('Logout API error:', error);
    } finally {
      clearAuth();
      navigate(ROUTES.LOGIN, { replace: true });
    }
  }, [clearAuth, navigate]);

  /**
   * Refresh access token
   */
  const refreshToken = useCallback(async () => {
    try {
      const response = await authService.refreshToken();
      const { access_token, expires_in } = response;
      
      useAuthStore.getState().updateToken(access_token, expires_in);
      return { success: true };
    } catch (error) {
      // If refresh fails, logout user
      clearAuth();
      navigate(ROUTES.LOGIN, { replace: true });
      return { success: false };
    }
  }, [clearAuth, navigate]);

  /**
   * Check if token needs refresh and refresh if necessary
   */
  const checkAndRefreshToken = useCallback(async () => {
    if (isTokenExpired()) {
      await refreshToken();
    }
  }, [isTokenExpired, refreshToken]);

  return {
    user,
    isAuthenticated,
    login,
    logout,
    refreshToken,
    checkAndRefreshToken,
  };
}
