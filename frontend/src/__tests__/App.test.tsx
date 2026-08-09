import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useAuthStore } from '../store/authStore';
import type { User } from '../types/auth';

// Test ProtectedRoute and PublicRoute logic by simulating routes
// Using MemoryRouter to avoid BrowserRouter window.location issues

import { MemoryRouter, Routes, Route, Navigate } from 'react-router-dom';

// Simplified versions of the route guards from App.tsx
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

const mockUser: User = {
  id: 1,
  username: 'admin',
  email: 'admin@test.com',
  full_name: 'Admin',
  role: 'Administrator',
  is_active: true,
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
};

describe('App route guards', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      tokenExpiry: null,
    });
  });

  it('ProtectedRoute redirects unauthenticated user to login', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<div data-testid="login">Login</div>} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div data-testid="dashboard">Dashboard</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('login')).toBeInTheDocument();
    expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument();
  });

  it('ProtectedRoute allows authenticated user', () => {
    useAuthStore.setState({ user: mockUser, isAuthenticated: true, token: 'tok' });
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<div data-testid="login">Login</div>} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div data-testid="dashboard">Dashboard</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
    expect(screen.queryByTestId('login')).not.toBeInTheDocument();
  });

  it('PublicRoute redirects authenticated user to dashboard', () => {
    useAuthStore.setState({ user: mockUser, isAuthenticated: true, token: 'tok' });
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route
            path="/login"
            element={
              <PublicRoute>
                <div data-testid="login">Login</div>
              </PublicRoute>
            }
          />
          <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
    expect(screen.queryByTestId('login')).not.toBeInTheDocument();
  });

  it('PublicRoute allows unauthenticated user', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route
            path="/login"
            element={
              <PublicRoute>
                <div data-testid="login">Login</div>
              </PublicRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('login')).toBeInTheDocument();
  });
});
