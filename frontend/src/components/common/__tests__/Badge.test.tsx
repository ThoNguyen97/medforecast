import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Badge, { StockStatusBadge, AlertSeverityBadge } from '../Badge';

describe('Badge', () => {
  it('renders children text', () => {
    render(<Badge>Test</Badge>);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('renders with default neutral variant', () => {
    render(<Badge>Neutral</Badge>);
    const badge = screen.getByText('Neutral');
    expect(badge.className).toMatch(/neutral/);
  });

  it('renders with danger variant', () => {
    render(<Badge variant="danger">Critical</Badge>);
    const badge = screen.getByText('Critical');
    expect(badge.className).toMatch(/danger/);
  });

  it('renders with success variant', () => {
    render(<Badge variant="success">OK</Badge>);
    const badge = screen.getByText('OK');
    expect(badge.className).toMatch(/success/);
  });

  it('renders dot when dot=true', () => {
    const { container } = render(<Badge dot>With dot</Badge>);
    // The dot is a sibling span
    const spans = container.querySelectorAll('span');
    expect(spans.length).toBeGreaterThan(1);
  });

  it('does not render dot by default', () => {
    const { container } = render(<Badge>No dot</Badge>);
    // Only one span (the badge itself)
    expect(container.querySelectorAll('span').length).toBe(1);
  });
});

describe('StockStatusBadge', () => {
  it('renders "An toàn" for safe status', () => {
    render(<StockStatusBadge status="safe" />);
    expect(screen.getByText('An toàn')).toBeInTheDocument();
  });

  it('renders "Thấp" for low status', () => {
    render(<StockStatusBadge status="low" />);
    expect(screen.getByText('Thấp')).toBeInTheDocument();
  });

  it('renders "Nguy hiểm" for critical status', () => {
    render(<StockStatusBadge status="critical" />);
    expect(screen.getByText('Nguy hiểm')).toBeInTheDocument();
  });
});

describe('AlertSeverityBadge', () => {
  it('renders "Nghiêm trọng" for critical', () => {
    render(<AlertSeverityBadge severity="critical" />);
    expect(screen.getByText('Nghiêm trọng')).toBeInTheDocument();
  });

  it('renders "Cao" for high', () => {
    render(<AlertSeverityBadge severity="high" />);
    expect(screen.getByText('Cao')).toBeInTheDocument();
  });

  it('renders "Trung bình" for medium', () => {
    render(<AlertSeverityBadge severity="medium" />);
    expect(screen.getByText('Trung bình')).toBeInTheDocument();
  });

  it('renders "Thấp" for low', () => {
    render(<AlertSeverityBadge severity="low" />);
    expect(screen.getByText('Thấp')).toBeInTheDocument();
  });
});
