import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import InventoryPage from '../Inventory';
import * as useInventoryHooks from '../../hooks/useInventory';
import type { Inventory } from '../../types/inventory';

// Mock complex child components
vi.mock('../../components/inventory/InventoryTable', () => ({
  default: ({ inventory }: { inventory: Inventory[] }) => (
    <div data-testid="inventory-table">{inventory.length} items</div>
  ),
}));
vi.mock('../../components/inventory/AIInsightPanel', () => ({
  default: () => <div data-testid="ai-insight-panel" />,
}));

const mockInventory: Inventory[] = [
  {
    id: 1,
    supply_id: 10,
    supply: {
      id: 10,
      name: 'Khẩu trang',
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
  },
];

function makeQueryResult<T>(data: T, overrides = {}) {
  return {
    data,
    isLoading: false,
    isError: false,
    isSuccess: true,
    refetch: vi.fn(),
    ...overrides,
  } as any;
}

function makeMutationResult(overrides = {}) {
  return {
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
    isSuccess: false,
    ...overrides,
  } as any;
}

describe('Inventory page', () => {
  beforeEach(() => {
    vi.spyOn(useInventoryHooks, 'useInventory').mockReturnValue(
      makeQueryResult(mockInventory)
    );
    vi.spyOn(useInventoryHooks, 'useUpdateInventory').mockReturnValue(
      makeMutationResult()
    );
  });

  it('renders page heading', () => {
    render(<InventoryPage />);
    expect(screen.getByText('Tồn kho Vật tư Y tế')).toBeInTheDocument();
  });

  it('renders inventory table', () => {
    render(<InventoryPage />);
    expect(screen.getByTestId('inventory-table')).toBeInTheDocument();
  });

  it('renders AI insight panel when inventory exists', () => {
    render(<InventoryPage />);
    expect(screen.getByTestId('ai-insight-panel')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    vi.spyOn(useInventoryHooks, 'useInventory').mockReturnValue(
      makeQueryResult(undefined, { isLoading: true, data: undefined })
    );
    render(<InventoryPage />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders refresh button', () => {
    render(<InventoryPage />);
    expect(screen.getByRole('button', { name: /làm mới/i })).toBeInTheDocument();
  });
});
