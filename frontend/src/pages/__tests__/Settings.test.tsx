import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Settings from '../Settings';
import { useAuthStore } from '../../store/authStore';
import * as useConfigHooks from '../../hooks/useConfig';
import type { User } from '../../types/auth';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, Navigate: ({ to }: { to: string }) => <div>Redirected to {to}</div> };
});

const adminUser: User = {
  id: 1,
  username: 'admin',
  email: 'admin@test.com',
  full_name: 'Admin',
  role: 'Administrator',
  is_active: true,
  created_at: '2024-01-01T00:00:00',
  updated_at: '2024-01-01T00:00:00',
};

const pharmacistUser: User = { ...adminUser, id: 2, role: 'Pharmacist' };

function makeQueryResult<T>(data: T) {
  return { data, isLoading: false, refetch: vi.fn() } as any;
}

function makeMutation() {
  return { mutateAsync: vi.fn(), isPending: false } as any;
}

function renderSettings() {
  return render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>
  );
}

describe('Settings page', () => {
  beforeEach(() => {
    vi.spyOn(useConfigHooks, 'useConfigs').mockReturnValue(makeQueryResult([]));
    vi.spyOn(useConfigHooks, 'useAuditLogs').mockReturnValue(makeQueryResult([]));
    vi.spyOn(useConfigHooks, 'useUpdateConfig').mockReturnValue(makeMutation());
  });

  it('renders page heading for admin', () => {
    useAuthStore.setState({ user: adminUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByText('Quản trị hệ thống')).toBeInTheDocument();
  });

  it('redirects non-admin users', () => {
    useAuthStore.setState({ user: pharmacistUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByText(/Redirected to/i)).toBeInTheDocument();
  });

  it('renders tab navigation', () => {
    useAuthStore.setState({ user: adminUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByRole('button', { name: /tham số dss/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /định mức thực nghiệm/i })).toBeInTheDocument();
    // 12/09/2026: ba tab nối vào bảng mà DSS không đọc đã gỡ
    expect(screen.queryByRole('button', { name: /ngưỡng cảnh báo/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /nhẹ\/tb\/nặng/i })).not.toBeInTheDocument();
  });

  it('shows admin-only badge', () => {
    useAuthStore.setState({ user: adminUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByText(/chỉ quản trị viên/i)).toBeInTheDocument();
  });
});
