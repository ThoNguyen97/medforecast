import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AIInsightPanel from '../AIInsightPanel';
import type { Inventory } from '../../../types/inventory';

const makeInventory = (id: number, status: 'safe' | 'low' | 'critical', stock = 500): Inventory => ({
  id,
  supply_id: id * 10,
  supply: {
    id: id * 10,
    name: `Supply ${id}`,
    category: 'mask',
    unit: 'cái',
    unit_price: 2000,
    minimum_order_quantity: 100,
    lead_time_days: 3,
    is_active: true,
    created_at: '2024-01-01T00:00:00',
    updated_at: '2024-01-01T00:00:00',
  },
  quantity_on_hand: stock,
  safety_stock_level: 100,
  reorder_point: 120,
  storage_capacity: 10000,
  last_updated: '2024-01-01T00:00:00',
  stock_status: status,
});

describe('AIInsightPanel', () => {
  it('renders panel title', () => {
    render(<AIInsightPanel inventory={[]} />);
    expect(screen.getByText(/Phân tích AI/i)).toBeInTheDocument();
  });

  it('shows critical item count', () => {
    const inventory = [
      makeInventory(1, 'critical', 50),
      makeInventory(2, 'critical', 30),
      makeInventory(3, 'safe', 500),
    ];
    render(<AIInsightPanel inventory={inventory} />);
    // "Nguy cơ cao" section shows critical count
    expect(screen.getByText('Nguy cơ cao')).toBeInTheDocument();
    // 2 critical items, check text "2" exists somewhere
    const allTwos = screen.getAllByText('2');
    expect(allTwos.length).toBeGreaterThanOrEqual(1);
  });

  it('shows low stock item count', () => {
    const inventory = [
      makeInventory(1, 'low', 80),
      makeInventory(2, 'low', 90),
    ];
    render(<AIInsightPanel inventory={inventory} />);
    // 2 low stock items
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1);
  });

  it('shows AI recommendation text', () => {
    render(<AIInsightPanel inventory={[makeInventory(1, 'critical', 50)]} />);
    expect(screen.getByText(/Khuyến nghị/i)).toBeInTheDocument();
  });

  it('shows high risk items list when present', () => {
    const inventory = [makeInventory(1, 'critical', 50)];
    render(<AIInsightPanel inventory={inventory} />);
    expect(screen.getByText('Supply 1')).toBeInTheDocument();
  });

  it('handles empty inventory', () => {
    render(<AIInsightPanel inventory={[]} />);
    // All zero counts shown
    const zeros = screen.getAllByText('0');
    expect(zeros.length).toBeGreaterThanOrEqual(1);
  });
});
