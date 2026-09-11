import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CriticalAlertsTable from '../CriticalAlertsTable';
import type { DashboardCriticalAlert } from '../../../types/dashboard';

const mockAlerts: DashboardCriticalAlert[] = [
  {
    id: 1,
    supply_name: 'Khẩu trang N95',
    severity: 'critical',
    shortage_date: '2024-02-15',
    current_stock: 50,
    required_stock: 500,
    message: 'Low stock critical',
  },
  {
    id: 2,
    supply_name: 'Găng tay y tế',
    severity: 'high',
    shortage_date: null,
    current_stock: null,
    required_stock: null,
    message: null,
  },
];

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderTable(alerts = mockAlerts) {
  return render(
    <MemoryRouter>
      <CriticalAlertsTable alerts={alerts} />
    </MemoryRouter>
  );
}

describe('CriticalAlertsTable', () => {
  it('renders table heading', () => {
    renderTable();
    expect(screen.getByText('Cảnh báo Nghiêm trọng')).toBeInTheDocument();
  });

  it('renders supply names', () => {
    renderTable();
    expect(screen.getByText('Khẩu trang N95')).toBeInTheDocument();
    expect(screen.getByText('Găng tay y tế')).toBeInTheDocument();
  });

  it('shows severity badges', () => {
    renderTable();
    expect(screen.getByText('Nghiêm trọng')).toBeInTheDocument();
    expect(screen.getByText('Cao')).toBeInTheDocument();
  });

  it('shows empty state when no alerts', () => {
    renderTable([]);
    expect(screen.getByText('Không có cảnh báo nghiêm trọng')).toBeInTheDocument();
  });

  it('shows "—" for null shortage date', () => {
    renderTable();
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('navigates to alerts page when "Xem tất cả" clicked', () => {
    renderTable();
    fireEvent.click(screen.getByRole('button', { name: /xem tất cả/i }));
    expect(mockNavigate).toHaveBeenCalled();
  });
});
