import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import PerformanceTable from '../PerformanceTable';
import type { ForecastAccuracyReport } from '../../../types/reports';

const mockData: ForecastAccuracyReport = {
  period: { start_date: '2024-01-01', end_date: '2024-01-31', period_days: 30 },
  summary: {
    total_forecasts: 30,
    avg_mae: 1.5,
    avg_rmse: 2.0,
    avg_mape: 5.5,
    best_model_by_mape: 'xgboost',
  },
  model_performance: [
    { model: 'xgboost', avg_mae: 1.2, avg_rmse: 1.8, avg_mape: 4.5, sample_count: 10 },
    { model: 'prophet', avg_mae: 1.8, avg_rmse: 2.3, avg_mape: 6.5, sample_count: 10 },
  ],
  filters: { disease_type: 'dengue_fever' },
  time_series: [
    { date: '2024-01-15', mae: 1.5, rmse: 2.0, mape: 5.5, model: 'xgboost', disease_type: 'dengue_fever' },
    { date: '2024-01-20', mae: 1.2, rmse: 1.8, mape: 4.8, model: 'xgboost', disease_type: 'dengue_fever' },
  ],
};

describe('PerformanceTable', () => {
  it('shows loading spinner when isLoading=true', () => {
    render(<PerformanceTable data={undefined} isLoading />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows empty state when no data', () => {
    render(<PerformanceTable data={undefined} isLoading={false} />);
    expect(screen.getByText(/không có dữ liệu/i)).toBeInTheDocument();
  });

  it('renders table heading', () => {
    render(<PerformanceTable data={mockData} isLoading={false} />);
    expect(screen.getByText('Hiệu suất Dự báo Theo Tháng')).toBeInTheDocument();
  });

  it('renders model performance cards', () => {
    render(<PerformanceTable data={mockData} isLoading={false} />);
    // model names rendered as-is in DOM (CSS uppercases them visually)
    expect(screen.getAllByText('xgboost').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('prophet').length).toBeGreaterThanOrEqual(1);
  });

  it('renders best model badge', () => {
    render(<PerformanceTable data={mockData} isLoading={false} />);
    expect(screen.getByText('Tốt nhất')).toBeInTheDocument();
  });

  it('renders monthly rows', () => {
    render(<PerformanceTable data={mockData} isLoading={false} />);
    // Month 1/2024 should appear
    expect(screen.getByText(/Tháng 1\/2024/)).toBeInTheDocument();
  });

  it('shows disease type filter indicator', () => {
    render(<PerformanceTable data={mockData} isLoading={false} />);
    // disease_type filter "dengue_fever" should appear as a badge
    expect(screen.getByText(/Sốt xuất huyết/)).toBeInTheDocument();
  });
});
