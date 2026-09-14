import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Reports from '../Reports';
import * as useReportsHooks from '../../hooks/useReports';

// Mock report sub-components
vi.mock('../../components/reports/ConsumptionReport', () => ({
  default: () => <div data-testid="consumption-report" />,
}));
vi.mock('../../components/reports/PerformanceTable', () => ({
  default: () => <div data-testid="performance-table" />,
}));
vi.mock('../../components/reports/ReportFilters', () => ({
  default: () => <div data-testid="report-filters" />,
}));
vi.mock('../../components/reports/ExportButton', () => ({
  default: () => <button data-testid="export-button">Export</button>,
}));

function makeQueryResult<T>(data: T, overrides = {}) {
  return {
    data,
    isLoading: false,
    isError: false,
    isSuccess: true,
    refetch: vi.fn(),
    ...overrides,
  } as any;
}

describe('Reports page', () => {
  beforeEach(() => {
    vi.spyOn(useReportsHooks, 'useConsumptionReport').mockReturnValue(makeQueryResult(null));
    vi.spyOn(useReportsHooks, 'useForecastAccuracyReport').mockReturnValue(makeQueryResult(null));
    vi.spyOn(useReportsHooks, 'useInventoryTurnoverReport').mockReturnValue(makeQueryResult(null));
  });

  it('renders page heading', () => {
    render(<Reports />);
    expect(screen.getByText('Báo cáo & Phân tích')).toBeInTheDocument();
  });

  it('renders tab navigation', () => {
    render(<Reports />);
    expect(screen.getByRole('button', { name: /tiêu thụ vật tư/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /độ chính xác dự báo/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /vòng quay tồn kho/i })).toBeInTheDocument();
  });

  it('shows consumption report by default', () => {
    render(<Reports />);
    expect(screen.getByTestId('consumption-report')).toBeInTheDocument();
  });

  it('switches to forecast accuracy report tab', () => {
    render(<Reports />);
    fireEvent.click(screen.getByRole('button', { name: /độ chính xác dự báo/i }));
    expect(screen.getByTestId('performance-table')).toBeInTheDocument();
  });

  it('renders export button', () => {
    render(<Reports />);
    expect(screen.getByTestId('export-button')).toBeInTheDocument();
  });

  it('renders refresh button', () => {
    render(<Reports />);
    expect(screen.getByRole('button', { name: /làm mới/i })).toBeInTheDocument();
  });

  it('shows guide panel', () => {
    render(<Reports />);
    expect(screen.getByText(/Hướng dẫn sử dụng báo cáo/i)).toBeInTheDocument();
  });
});
