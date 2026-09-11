import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import Epidemiology from '../Epidemiology';
import * as useEpidemiology from '../../hooks/useEpidemiology';

// Mock chart components to avoid recharts setup
vi.mock('../../components/epidemiology/DiseaseTrendsChart', () => ({
  default: () => <div data-testid="trends-chart" />,
}));
vi.mock('../../components/epidemiology/RecentCasesTable', () => ({
  default: () => <div data-testid="recent-cases-table" />,
}));
vi.mock('../../components/epidemiology/StatisticsCards', () => ({
  default: () => <div data-testid="stats-cards" />,
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

describe('Epidemiology page', () => {
  beforeEach(() => {
    vi.spyOn(useEpidemiology, 'useDiseaseStatistics').mockReturnValue(
      makeQueryResult({ statistics: [{ disease_type: 'dengue_fever', count: 100 }] })
    );
    vi.spyOn(useEpidemiology, 'useDiseaseTrends').mockReturnValue(
      makeQueryResult({ trends: [] })
    );
    vi.spyOn(useEpidemiology, 'useDiseaseCases').mockReturnValue(
      makeQueryResult([])
    );
  });

  it('renders page heading', () => {
    render(<Epidemiology />);
    expect(screen.getByText('Dữ liệu Dịch tễ học')).toBeInTheDocument();
  });

  it('renders trends chart when data available', () => {
    render(<Epidemiology />);
    expect(screen.getByTestId('trends-chart')).toBeInTheDocument();
  });

  it('renders statistics cards', () => {
    render(<Epidemiology />);
    expect(screen.getByTestId('stats-cards')).toBeInTheDocument();
  });

  it('renders recent cases table', () => {
    render(<Epidemiology />);
    expect(screen.getByTestId('recent-cases-table')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    vi.spyOn(useEpidemiology, 'useDiseaseStatistics').mockReturnValue(
      makeQueryResult(undefined, { isLoading: true, data: undefined })
    );
    vi.spyOn(useEpidemiology, 'useDiseaseTrends').mockReturnValue(
      makeQueryResult(undefined, { isLoading: true, data: undefined })
    );
    vi.spyOn(useEpidemiology, 'useDiseaseCases').mockReturnValue(
      makeQueryResult(undefined, { isLoading: true, data: undefined })
    );
    render(<Epidemiology />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders refresh button', () => {
    render(<Epidemiology />);
    expect(screen.getByRole('button', { name: /làm mới/i })).toBeInTheDocument();
  });
});
