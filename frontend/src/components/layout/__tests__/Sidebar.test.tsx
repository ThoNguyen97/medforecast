import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '../Sidebar';
import { useAuthStore } from '../../../store/authStore';
import { useUIStore } from '../../../store/uiStore';
import type { User } from '../../../types/auth';

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

function renderSidebar() {
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>
  );
}

describe('Sidebar', () => {
  beforeEach(() => {
    useUIStore.setState({ isSidebarCollapsed: false });
  });

  it('renders navigation links', () => {
    useAuthStore.setState({ user: adminUser });
    renderSidebar();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Tồn kho')).toBeInTheDocument();
    expect(screen.getByText('Dự báo')).toBeInTheDocument();
    expect(screen.getByText('Cảnh báo')).toBeInTheDocument();
  });

  it('shows Settings link for admin', () => {
    useAuthStore.setState({ user: adminUser });
    renderSidebar();
    expect(screen.getByText('Cài đặt')).toBeInTheDocument();
  });

  it('hides Settings link for non-admin', () => {
    useAuthStore.setState({ user: pharmacistUser });
    renderSidebar();
    expect(screen.queryByText('Cài đặt')).not.toBeInTheDocument();
  });

  it('shows app name when expanded', () => {
    useAuthStore.setState({ user: adminUser });
    useUIStore.setState({ isSidebarCollapsed: false });
    renderSidebar();
    expect(screen.getByText('MedForecast AI')).toBeInTheDocument();
  });

  it('hides app name when collapsed', () => {
    useAuthStore.setState({ user: adminUser });
    useUIStore.setState({ isSidebarCollapsed: true });
    renderSidebar();
    expect(screen.queryByText('MedForecast AI')).not.toBeInTheDocument();
  });

  it('toggles collapse on button click', () => {
    useAuthStore.setState({ user: adminUser });
    renderSidebar();
    const collapseBtn = screen.getByTitle('Thu gọn');
    fireEvent.click(collapseBtn);
    expect(useUIStore.getState().isSidebarCollapsed).toBe(true);
  });
});
