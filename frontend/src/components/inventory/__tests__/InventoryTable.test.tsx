import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import InventoryTable from '../InventoryTable';
import type { Inventory } from '../../../types/inventory';

const makeInventory = (id: number, status: 'safe' | 'low' | 'critical' = 'safe'): Inventory => ({
  id,
  supply_id: id * 10,
  supply: {
    id: id * 10,
    name: `Vật tư ${id}`,
    category: 'mask',
    unit: 'cái',
    unit_price: 2000,
    minimum_order_quantity: 100,
    lead_time_days: 5,
    is_active: true,
    created_at: '2024-01-01T00:00:00',
    updated_at: '2024-01-01T00:00:00',
  },
  quantity_on_hand: status === 'critical' ? 50 : status === 'low' ? 150 : 500,
  safety_stock_level: 100,
  reorder_point: 120,
  storage_capacity: 10000,
  last_updated: '2024-01-01T00:00:00',
  stock_status: status,
});

describe('InventoryTable', () => {
  it('shows loading text when isLoading=true', () => {
    render(<InventoryTable inventory={[]} onUpdateStock={vi.fn()} isLoading />);
    expect(screen.getByText('Đang tải dữ liệu...')).toBeInTheDocument();
  });

  it('shows empty state when no inventory', () => {
    render(<InventoryTable inventory={[]} onUpdateStock={vi.fn()} />);
    expect(screen.getByText('Không có dữ liệu tồn kho')).toBeInTheDocument();
  });

  it('renders supply names', () => {
    render(
      <InventoryTable
        inventory={[makeInventory(1), makeInventory(2)]}
        onUpdateStock={vi.fn()}
      />
    );
    expect(screen.getByText('Vật tư 1')).toBeInTheDocument();
    expect(screen.getByText('Vật tư 2')).toBeInTheDocument();
  });

  it('renders stock status badge', () => {
    render(<InventoryTable inventory={[makeInventory(1, 'critical')]} onUpdateStock={vi.fn()} />);
    expect(screen.getByText('Nguy cơ')).toBeInTheDocument();
  });

  it('renders lead time', () => {
    render(<InventoryTable inventory={[makeInventory(1)]} onUpdateStock={vi.fn()} />);
    expect(screen.getByText('5 ngày')).toBeInTheDocument();
  });

  it('calls onUpdateStock when update button clicked', () => {
    const onUpdateStock = vi.fn();
    const item = makeInventory(1);
    render(<InventoryTable inventory={[item]} onUpdateStock={onUpdateStock} />);
    fireEvent.click(screen.getByRole('button', { name: /cập nhật/i }));
    expect(onUpdateStock).toHaveBeenCalledWith(item);
  });

  it('shows risk level Cao for critical items', () => {
    render(<InventoryTable inventory={[makeInventory(1, 'critical')]} onUpdateStock={vi.fn()} />);
    expect(screen.getByText('Cao')).toBeInTheDocument();
  });

  it('shows risk level Trung bình for low items', () => {
    render(<InventoryTable inventory={[makeInventory(1, 'low')]} onUpdateStock={vi.fn()} />);
    expect(screen.getByText('Trung bình')).toBeInTheDocument();
  });

  it('shows risk level Thấp for safe items', () => {
    render(<InventoryTable inventory={[makeInventory(1, 'safe')]} onUpdateStock={vi.fn()} />);
    expect(screen.getByText('Thấp')).toBeInTheDocument();
  });
});
