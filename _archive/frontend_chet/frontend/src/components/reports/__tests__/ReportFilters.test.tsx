import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ReportFiltersComponent from '../ReportFilters';

describe('ReportFiltersComponent', () => {
  it('renders date inputs', () => {
    render(
      <ReportFiltersComponent
        filters={{}}
        reportType="consumption"
        onChange={vi.fn()}
      />
    );
    // Two date inputs in the component
    const inputs = document.querySelectorAll('input[type="date"]');
    expect(inputs.length).toBe(2);
  });

  it('renders category filter for consumption report', () => {
    render(
      <ReportFiltersComponent
        filters={{}}
        reportType="consumption"
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Danh mục')).toBeInTheDocument();
  });

  it('renders category filter for inventory-turnover report', () => {
    render(
      <ReportFiltersComponent
        filters={{}}
        reportType="inventory-turnover"
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Danh mục')).toBeInTheDocument();
  });

  it('renders disease type filter for forecast-accuracy report', () => {
    render(
      <ReportFiltersComponent
        filters={{}}
        reportType="forecast-accuracy"
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Loại bệnh')).toBeInTheDocument();
  });

  it('renders model filter for forecast-accuracy report', () => {
    render(
      <ReportFiltersComponent
        filters={{}}
        reportType="forecast-accuracy"
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('Mô hình')).toBeInTheDocument();
  });

  it('does not show disease type filter for consumption report', () => {
    render(
      <ReportFiltersComponent
        filters={{}}
        reportType="consumption"
        onChange={vi.fn()}
      />
    );
    expect(screen.queryByText('Loại bệnh')).not.toBeInTheDocument();
  });

  it('calls onChange when date changes', () => {
    const onChange = vi.fn();
    render(
      <ReportFiltersComponent
        filters={{}}
        reportType="consumption"
        onChange={onChange}
      />
    );
    const dateInputs = screen.getAllByDisplayValue('');
    fireEvent.change(dateInputs[0], { target: { value: '2024-01-01' } });
    expect(onChange).toHaveBeenCalled();
  });
});
