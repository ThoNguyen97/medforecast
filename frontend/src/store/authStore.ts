import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types/auth';
import { TOKEN_KEY, REFRESH_TOKEN_KEY, USER_KEY, TOKEN_EXPIRY_KEY } from '../utils/constants';

interface AuthStore {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  tokenExpiry: number | null;

  // Actions
  setAuth: (user: User, token: string, refreshToken: string, expiresIn: number) => void;
  updateToken: (token: string, expiresIn: number) => void;
  logout: () => void;
  isTokenExpired: () => boolean;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      tokenExpiry: null,

      setAuth: (user, token, refreshToken, expiresIn) => {
        const tokenExpiry = Date.now() + expiresIn * 1000;

        // Also store in localStorage for Axios interceptor
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        localStorage.setItem(TOKEN_EXPIRY_KEY, tokenExpiry.toString());

        set({
          user,
          token,
          refreshToken,
          isAuthenticated: true,
          tokenExpiry,
        });
      },

      updateToken: (token, expiresIn) => {
        const tokenExpiry = Date.now() + expiresIn * 1000;
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(TOKEN_EXPIRY_KEY, tokenExpiry.toString());
        set({ token, tokenExpiry });
      },

      logout: () => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
        localStorage.removeItem(TOKEN_EXPIRY_KEY);

        set({
          user: null,
          token: null,
          refreshToken: null,
          isAuthenticated: false,
          tokenExpiry: null,
        });
      },

      isTokenExpired: () => {
        const { tokenExpiry } = get();
        if (!tokenExpiry) return true;
        // Consider expired 5 minutes before actual expiry
        return Date.now() > tokenExpiry - 5 * 60 * 1000;
      },
    }),
    {
      name: 'medforecast-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
        tokenExpiry: state.tokenExpiry,
      }),
    }
  )
);
