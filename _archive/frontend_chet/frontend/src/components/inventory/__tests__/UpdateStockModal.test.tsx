import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import UpdateStockModal from '../UpdateStockModal';
import type { Inventory } from '../../../types/inventory';

const mockInventory: Inventory = {
  id: 1,
  supply_id: 10,
  supply: {
    id: 10,
    name: 'Khẩu trang y tế',
    category: 'mask',
    unit: 'cái',
    unit_price: 2000,
    minimum_order_quantity: 100,
    lead_time_days: 3,
    is_active: true,
    created_at: '2024-01-01T00:00:00',
    updated_at: '2024-01-01T00:00:00',
  },
  quantity_on_hand: 500,
  safety_stock_level: 100,
  reorder_point: 150,
  storage_capacity: 10000,
  last_updated: '2024-01-01T00:00:00',
  stock_status: 'safe',
};

describe('UpdateStockModal', () => {
  it('does not render when inventory is null', () => {
    render(
      <UpdateStockModal
        isOpen={true}
        onClose={vi.fn()}
        inventory={null}
        onUpdate={vi.fn()}
      />
    );
    expect(screen.queryByText('Cập nhật Tồn kho')).not.toBeInTheDocument();
  });

  it('renders supply name', () => {
    render(
      <UpdateStockModal
        isOpen={true}
        onClose={vi.fn()}
        inventory={mockInventory}
        onUpdate={vi.fn()}
      />
    );
    expect(screen.getByText('Khẩu trang y tế')).toBeInTheDocument();
  });

  it('prefills current stock from inventory', () => {
    render(
      <UpdateStockModal
        isOpen={true}
        onClose={vi.fn()}
        inventory={mockInventory}
        onUpdate={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/số lượng hiện tại/i) as HTMLInputElement;
    expect(input.value).toBe('500');
  });

  it('prefills safety stock from inventory', () => {
    render(
      <UpdateStockModal
        isOpen={true}
        onClose={vi.fn()}
        inventory={mockInventory}
        onUpdate={vi.fn()}
      />
    );
    const input = screen.getByLabelText(/mức tồn kho an toàn/i) as HTMLInputElement;
    expect(input.value).toBe('100');
  });

  it('calls onUpdate with new values on submit', () => {
    const onUpdate = vi.fn();
    render(
      <UpdateStockModal
        isOpen={true}
        onClose={vi.fn()}
        inventory={mockInventory}
        onUpdate={onUpdate}
      />
    );
    const stockInput = screen.getByLabelText(/số lượng hiện tại/i);
    fireEvent.change(stockInput, { target: { value: '800' } });
    fireEvent.submit(stockInput.closest('form')!);
    expect(onUpdate).toHaveBeenCalledWith(1, { quantity_on_hand: 800 });
  });

  it('calls onClose when cancel button clicked', () => {
    const onClose = vi.fn();
    render(
      <UpdateStockModal
        isOpen={true}
        onClose={onClose}
        inventory={mockInventory}
        onUpdate={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /hủy/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('disables submit button when isLoading=true', () => {
    render(
      <UpdateStockModal
        isOpen={true}
        onClose={vi.fn()}
        inventory={mockInventory}
        onUpdate={vi.fn()}
        isLoading={true}
      />
    );
    expect(screen.getByRole('button', { name: /đang cập nhật/i })).toBeDisabled();
  });
});
