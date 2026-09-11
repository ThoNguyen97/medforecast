import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DiseaseTrendsChart from '../DiseaseTrendsChart';
import type { DiseaseTrendPoint } from '../../../types/epidemiology';

describe('DiseaseTrendsChart', () => {
  it('renders heading', () => {
    render(<DiseaseTrendsChart trends={[]} />);
    expect(screen.getByText('Xu hướng Ca bệnh')).toBeInTheDocument();
  });

  it('shows empty state when no trends', () => {
    render(<DiseaseTrendsChart trends={[]} />);
    expect(screen.getByText('Không có dữ liệu xu hướng')).toBeInTheDocument();
  });

  it('renders chart when trends provided', () => {
    const trends: DiseaseTrendPoint[] = [
      { date: '2024-01-01', case_count: 10, disease_type: 'dengue_fever' },
      { date: '2024-01-02', case_count: 15, disease_type: 'dengue_fever' },
    ];
    render(<DiseaseTrendsChart trends={trends} />);
    expect(screen.queryByText('Không có dữ liệu')).not.toBeInTheDocument();
  });

  it('renders with selected disease type filter', () => {
    const trends: DiseaseTrendPoint[] = [
      { date: '2024-01-01', case_count: 10, disease_type: 'dengue_fever' },
    ];
    render(<DiseaseTrendsChart trends={trends} selectedDiseaseType="dengue_fever" />);
    expect(screen.getByText('Xu hướng Ca bệnh')).toBeInTheDocument();
  });
});
