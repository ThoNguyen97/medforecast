import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Button from '../Button';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when isLoading is true', () => {
    render(<Button isLoading>Loading</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('shows loading spinner when isLoading is true', () => {
    render(<Button isLoading>Save</Button>);
    // The role="status" is on the LoadingSpinner
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders left icon', () => {
    render(<Button leftIcon={<span data-testid="left-icon" />}>With icon</Button>);
    expect(screen.getByTestId('left-icon')).toBeInTheDocument();
  });

  it('renders right icon', () => {
    render(<Button rightIcon={<span data-testid="right-icon" />}>With icon</Button>);
    expect(screen.getByTestId('right-icon')).toBeInTheDocument();
  });

  it('hides right icon when loading', () => {
    render(<Button isLoading rightIcon={<span data-testid="right-icon" />}>Saving</Button>);
    expect(screen.queryByTestId('right-icon')).not.toBeInTheDocument();
  });

  it('applies variant class', () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole('button').className).toMatch(/danger/);
  });

  it('applies size class', () => {
    render(<Button size="lg">Large</Button>);
    expect(screen.getByRole('button').className).toMatch(/py-2\.5|text-base/);
  });

  it('applies custom className', () => {
    render(<Button className="custom-class">Custom</Button>);
    expect(screen.getByRole('button').className).toContain('custom-class');
  });
});
