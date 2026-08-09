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
    vi.spyOn(useConfigHooks, 'useConversionRatios').mockReturnValue(makeQueryResult([]));
    vi.spyOn(useConfigHooks, 'useThresholds').mockReturnValue(makeQueryResult([]));
    vi.spyOn(useConfigHooks, 'useAuditLogs').mockReturnValue(makeQueryResult([]));
    vi.spyOn(useConfigHooks, 'useUpdateConfig').mockReturnValue(makeMutation());
    vi.spyOn(useConfigHooks, 'useUpdateConversionRatios').mockReturnValue(makeMutation());
    vi.spyOn(useConfigHooks, 'useUpdateThresholds').mockReturnValue(makeMutation());
  });

  it('renders page heading for admin', () => {
    useAuthStore.setState({ user: adminUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByText('Cài đặt Hệ thống')).toBeInTheDocument();
  });

  it('redirects non-admin users', () => {
    useAuthStore.setState({ user: pharmacistUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByText(/Redirected to/i)).toBeInTheDocument();
  });

  it('renders tab navigation', () => {
    useAuthStore.setState({ user: adminUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByRole('button', { name: /ngưỡng cảnh báo/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /tỷ lệ quy đổi/i })).toBeInTheDocument();
  });

  it('shows admin-only badge', () => {
    useAuthStore.setState({ user: adminUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByText(/chỉ dành cho admin/i)).toBeInTheDocument();
  });

  it('shows warning banner', () => {
    useAuthStore.setState({ user: adminUser, isAuthenticated: true });
    renderSettings();
    expect(screen.getByText(/Thay đổi cấu hình sẽ ảnh hưởng/i)).toBeInTheDocument();
  });
});
