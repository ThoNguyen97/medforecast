import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Layout from '../Layout';
import { useUIStore } from '../../../store/uiStore';
import { useAuthStore } from '../../../store/authStore';
import type { User } from '../../../types/auth';

// Mock child components to keep tests focused
vi.mock('../Sidebar', () => ({
  default: () => <aside data-testid="sidebar">Sidebar</aside>,
}));
vi.mock('../Header', () => ({
  default: () => <header data-testid="header">Header</header>,
}));

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

describe('Layout', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: mockUser, isAuthenticated: true });
    useUIStore.setState({ isSidebarOpen: true });
  });

  it('renders sidebar', () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<Layout />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
  });

  it('renders header', () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<Layout />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('header')).toBeInTheDocument();
  });

  it('renders main content area', () => {
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<div data-testid="child">Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('child')).toBeInTheDocument();
  });
});
