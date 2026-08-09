import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ConsumptionReport from '../ConsumptionReport';
import type { ConsumptionReport as ConsumptionReportType } from '../../../types/reports';

const mockData: ConsumptionReportType = {
  period: { start_date: '2024-01-01', end_date: '2024-01-31', period_days: 30 },
  summary: {
    total_required_across_all_categories: 5000,
    categories_count: 2,
    top_category: 'mask',
  },
  categories: [
    {
      category: 'mask',
      total_required: 3000,
      supplies: [
        {
          supply_id: 1,
          supply_name: 'Khẩu trang N95',
          unit: 'cái',
          total_required: 3000,
          avg_daily_consumption: 100,
          active_days: 30,
        },
      ],
    },
    {
      category: 'glove',
      total_required: 2000,
      supplies: [
        {
          supply_id: 2,
          supply_name: 'Găng tay y tế',
          unit: 'đôi',
          total_required: 2000,
          avg_daily_consumption: 66.7,
          active_days: 30,
        },
      ],
    },
  ],
};

describe('ConsumptionReport', () => {
  it('shows loading spinner when isLoading=true', () => {
    render(<ConsumptionReport data={undefined} isLoading />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows empty state when no data', () => {
    render(<ConsumptionReport data={undefined} isLoading={false} />);
    expect(screen.getByText(/không có dữ liệu/i)).toBeInTheDocument();
  });

  it('shows empty state when categories is empty', () => {
    const emptyData = { ...mockData, categories: [] };
    render(<ConsumptionReport data={emptyData} isLoading={false} />);
    expect(screen.getByText(/không có dữ liệu/i)).toBeInTheDocument();
  });

  it('renders supply names in table', () => {
    render(<ConsumptionReport data={mockData} isLoading={false} />);
    expect(screen.getByText('Khẩu trang N95')).toBeInTheDocument();
    expect(screen.getByText('Găng tay y tế')).toBeInTheDocument();
  });

  it('renders report period', () => {
    render(<ConsumptionReport data={mockData} isLoading={false} />);
    expect(screen.getByText(/2024-01-01/)).toBeInTheDocument();
    expect(screen.getByText(/2024-01-31/)).toBeInTheDocument();
  });
});
