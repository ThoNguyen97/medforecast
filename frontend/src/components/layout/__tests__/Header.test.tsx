import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Header from '../Header';
import { useAuthStore } from '../../../store/authStore';
import { useUIStore } from '../../../store/uiStore';
import { useAuth } from '../../../hooks/useAuth';
import type { User } from '../../../types/auth';

vi.mock('../../../hooks/useAuth');

const mockUser: User = {
  id: 1,
  username: 'admin',
  email: 'admin@test.com',
  full_name: 'Nguyen Van A',
  role: 'Administrator',
  is_active: true,
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
};

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderHeader() {
  return render(
    <MemoryRouter>
      <Header />
    </MemoryRouter>
  );
}

describe('Header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      refreshToken: vi.fn(),
      checkAndRefreshToken: vi.fn(),
    });
    useUIStore.setState({ pageTitle: 'Test Page', unreadNotificationsCount: 0 });
  });

  it('renders page title', () => {
    renderHeader();
    expect(screen.getByText('Test Page')).toBeInTheDocument();
  });

  it('renders user full name', () => {
    renderHeader();
    expect(screen.getByText('Nguyen Van A')).toBeInTheDocument();
  });

  it('renders user initials in avatar', () => {
    renderHeader();
    // Full name "Nguyen Van A" → last 2 initials are "VA"
    expect(screen.getByText('VA')).toBeInTheDocument();
  });

  it('renders notification bell button', () => {
    renderHeader();
    expect(screen.getByLabelText('Thông báo')).toBeInTheDocument();
  });

  it('shows notification count badge when unread > 0', () => {
    useUIStore.setState({ unreadNotificationsCount: 3 });
    renderHeader();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('does not show badge when unread count is 0', () => {
    useUIStore.setState({ unreadNotificationsCount: 0 });
    renderHeader();
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  it('opens user dropdown on button click', () => {
    renderHeader();
    // Find user dropdown button by locating the avatar div container
    const dropdownButton = screen.getByText('Nguyen Van A').closest('button')!;
    fireEvent.click(dropdownButton);
    expect(screen.getByText('Đăng xuất')).toBeInTheDocument();
  });

  it('calls logout when logout button clicked', async () => {
    const mockLogout = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useAuth).mockReturnValue({
      user: mockUser,
      isAuthenticated: true,
      login: vi.fn(),
      logout: mockLogout,
      refreshToken: vi.fn(),
      checkAndRefreshToken: vi.fn(),
    });
    renderHeader();
    const dropdownButton = screen.getByText('Nguyen Van A').closest('button')!;
    fireEvent.click(dropdownButton);
    fireEvent.click(screen.getByText('Đăng xuất'));
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });
});
