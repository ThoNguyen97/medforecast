import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StatisticsCards from '../StatisticsCards';
import type { DiseaseStatistic } from '../../../types/epidemiology';

const mockStats: DiseaseStatistic[] = [
  {
    disease_type: 'dengue_fever',
    total_cases: 150,
    record_count: 30,
    latest_record_date: '2024-01-15',
    avg_cases_per_day: 5.0,
  },
  {
    disease_type: 'seasonal_flu',
    total_cases: 300,
    record_count: 30,
    latest_record_date: '2024-01-15',
    avg_cases_per_day: 10.0,
  },
];

describe('StatisticsCards', () => {
  it('renders total cases', () => {
    render(<StatisticsCards statistics={mockStats} />);
    // 150 + 300 = 450 total
    expect(screen.getByText('450')).toBeInTheDocument();
  });

  it('renders number of disease types', () => {
    render(<StatisticsCards statistics={mockStats} />);
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('renders highest disease count', () => {
    render(<StatisticsCards statistics={mockStats} />);
    // seasonal_flu has 300 cases (highest)
    expect(screen.getByText('300')).toBeInTheDocument();
  });

  it('renders average per day', () => {
    render(<StatisticsCards statistics={mockStats} />);
    // 5 + 10 = 15 avg per day
    expect(screen.getByText('15')).toBeInTheDocument();
  });

  it('renders card titles', () => {
    render(<StatisticsCards statistics={mockStats} />);
    expect(screen.getByText('Tổng ca bệnh')).toBeInTheDocument();
    expect(screen.getByText('Loại dịch bệnh')).toBeInTheDocument();
  });
});
