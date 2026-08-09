import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import RecentCasesTable from '../RecentCasesTable';
import type { DiseaseCase } from '../../../types/epidemiology';

const mockCase: DiseaseCase = {
  id: 1,
  recorded_at: '2024-01-15T08:00:00',
  disease_type: 'dengue_fever',
  case_count: 25,
  location: 'TP. Hồ Chí Minh',
  severity: 'moderate',
  data_source: 'Ministry of Health',
  created_at: '2024-01-15T08:00:00',
};

describe('RecentCasesTable', () => {
  it('renders table heading', () => {
    render(<RecentCasesTable cases={[]} />);
    expect(screen.getByText('Ca bệnh Gần đây')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    render(<RecentCasesTable cases={[]} isLoading />);
    expect(screen.getByText('Đang tải...')).toBeInTheDocument();
  });

  it('shows empty state when no cases', () => {
    render(<RecentCasesTable cases={[]} />);
    expect(screen.getByText('Không có dữ liệu ca bệnh')).toBeInTheDocument();
  });

  it('renders case row data', () => {
    render(<RecentCasesTable cases={[mockCase]} />);
    expect(screen.getByText('Sốt xuất huyết')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument();
    expect(screen.getByText('TP. Hồ Chí Minh')).toBeInTheDocument();
  });

  it('renders disease type badge', () => {
    render(<RecentCasesTable cases={[mockCase]} />);
    expect(screen.getByText('Sốt xuất huyết')).toBeInTheDocument();
  });

  it('renders data source', () => {
    render(<RecentCasesTable cases={[mockCase]} />);
    expect(screen.getByText('Ministry of Health')).toBeInTheDocument();
  });

  it('shows "—" for missing severity', () => {
    const caseNoSeverity = { ...mockCase, severity: undefined };
    render(<RecentCasesTable cases={[caseNoSeverity]} />);
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(1);
  });
});
