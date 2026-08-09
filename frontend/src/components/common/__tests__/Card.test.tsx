import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Card, { CardHeader, MetricCard } from '../Card';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>Content here</Card>);
    expect(screen.getByText('Content here')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(<Card className="custom">Child</Card>);
    expect(container.firstChild).toHaveClass('custom');
  });

  it('applies padding classes', () => {
    const { container } = render(<Card padding="lg">Child</Card>);
    expect(container.firstChild).toHaveClass('p-8');
  });

  it('applies no padding when padding="none"', () => {
    const { container } = render(<Card padding="none">Child</Card>);
    expect(container.firstChild).not.toHaveClass('p-4', 'p-6', 'p-8');
  });

  it('applies hover class when hover=true', () => {
    const { container } = render(<Card hover>Child</Card>);
    expect(container.firstChild).toHaveClass('cursor-pointer');
  });
});

describe('CardHeader', () => {
  it('renders title', () => {
    render(<CardHeader title="My Title" />);
    expect(screen.getByText('My Title')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<CardHeader title="T" subtitle="Sub" />);
    expect(screen.getByText('Sub')).toBeInTheDocument();
  });

  it('does not render subtitle when not provided', () => {
    render(<CardHeader title="T" />);
    expect(screen.queryByText('Sub')).not.toBeInTheDocument();
  });

  it('renders action when provided', () => {
    render(<CardHeader title="T" action={<button>Action</button>} />);
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument();
  });
});

describe('MetricCard', () => {
  it('renders title and value', () => {
    render(<MetricCard title="Total" value={42} />);
    expect(screen.getByText('Total')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders string value', () => {
    render(<MetricCard title="Status" value="OK" />);
    expect(screen.getByText('OK')).toBeInTheDocument();
  });

  it('renders subtitle when provided', () => {
    render(<MetricCard title="T" value={0} subtitle="Last 30 days" />);
    expect(screen.getByText('Last 30 days')).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    render(<MetricCard title="T" value={0} icon={<span data-testid="icon" />} />);
    expect(screen.getByTestId('icon')).toBeInTheDocument();
  });

  it('renders trend with up direction', () => {
    render(
      <MetricCard
        title="T"
        value={0}
        trend={{ value: 5, label: 'vs last month', direction: 'up' }}
      />
    );
    expect(screen.getByText('vs last month')).toBeInTheDocument();
    expect(screen.getByText(/5%/)).toBeInTheDocument();
  });

  it('renders trend with down direction', () => {
    render(
      <MetricCard
        title="T"
        value={0}
        trend={{ value: 3, label: 'vs last week', direction: 'down' }}
      />
    );
    expect(screen.getByText(/3%/)).toBeInTheDocument();
  });
});
