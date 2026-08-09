import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MetricCard from '../MetricCard';

describe('MetricCard', () => {
  it('renders title', () => {
    render(<MetricCard title="Total Supplies" value={120} icon={<span />} />);
    expect(screen.getByText('Total Supplies')).toBeInTheDocument();
  });

  it('renders numeric value', () => {
    render(<MetricCard title="T" value={999} icon={<span />} />);
    expect(screen.getByText('999')).toBeInTheDocument();
  });

  it('renders string value', () => {
    render(<MetricCard title="T" value="High" icon={<span />} />);
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('renders icon', () => {
    render(<MetricCard title="T" value={0} icon={<span data-testid="icon" />} />);
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<MetricCard title="T" value={0} icon={<span />} subtitle="Updated 5m ago" />);
    expect(screen.getByText('Updated 5m ago')).toBeInTheDocument();
  });

  it('renders trend with up arrow', () => {
    render(
      <MetricCard
        title="T"
        value={0}
        icon={<span />}
        trend={{ value: 12, label: 'vs last month', direction: 'up' }}
      />
    );
    expect(screen.getByText(/↑/)).toBeInTheDocument();
    expect(screen.getByText('vs last month')).toBeInTheDocument();
  });

  it('renders trend with down arrow', () => {
    render(
      <MetricCard
        title="T"
        value={0}
        icon={<span />}
        trend={{ value: 8, label: 'decrease', direction: 'down' }}
      />
    );
    expect(screen.getByText(/↓/)).toBeInTheDocument();
  });

  it('renders trend with neutral arrow', () => {
    render(
      <MetricCard
        title="T"
        value={0}
        icon={<span />}
        trend={{ value: 0, label: 'no change', direction: 'neutral' }}
      />
    );
    expect(screen.getByText(/→/)).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <MetricCard title="T" value={0} icon={<span />} className="my-card" />
    );
    expect(container.firstChild).toHaveClass('my-card');
  });
});
