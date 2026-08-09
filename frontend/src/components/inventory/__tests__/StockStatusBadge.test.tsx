import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import StockStatusBadge from '../StockStatusBadge';

describe('StockStatusBadge', () => {
  it('renders "An toàn" for safe status', () => {
    render(<StockStatusBadge status="safe" />);
    expect(screen.getByText('An toàn')).toBeInTheDocument();
  });

  it('applies green styling for safe', () => {
    render(<StockStatusBadge status="safe" />);
    const el = screen.getByText('An toàn');
    expect(el.className).toMatch(/green/);
  });

  it('renders "Sắp hết" for low status', () => {
    render(<StockStatusBadge status="low" />);
    expect(screen.getByText('Sắp hết')).toBeInTheDocument();
  });

  it('applies yellow styling for low', () => {
    render(<StockStatusBadge status="low" />);
    const el = screen.getByText('Sắp hết');
    expect(el.className).toMatch(/yellow/);
  });

  it('renders "Nguy cơ" for critical status', () => {
    render(<StockStatusBadge status="critical" />);
    expect(screen.getByText('Nguy cơ')).toBeInTheDocument();
  });

  it('applies red styling for critical', () => {
    render(<StockStatusBadge status="critical" />);
    const el = screen.getByText('Nguy cơ');
    expect(el.className).toMatch(/red/);
  });

  it('accepts custom className', () => {
    render(<StockStatusBadge status="safe" className="extra" />);
    const el = screen.getByText('An toàn');
    expect(el.className).toContain('extra');
  });
});
