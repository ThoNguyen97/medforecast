import { useState, useEffect } from 'react';
import Modal from '../common/Modal';
import Button from '../common/Button';
import type { Inventory } from '../../types/inventory';

interface UpdateStockModalProps {
  isOpen: boolean;
  onClose: () => void;
  inventory: Inventory | null;
  onUpdate: (id: number, data: { quantity_on_hand: number; safety_stock_level?: number }) => void;
  isLoading?: boolean;
}

export default function UpdateStockModal({
  isOpen,
  onClose,
  inventory,
  onUpdate,
  isLoading = false,
}: UpdateStockModalProps) {
  const [currentStock, setCurrentStock] = useState<string>('');
  const [safetyStock, setSafetyStock] = useState<string>('');

  useEffect(() => {
    if (inventory) {
      setCurrentStock((inventory.quantity_on_hand ?? inventory.current_stock ?? 0).toString());
      setSafetyStock((inventory.safety_stock_level ?? inventory.safety_stock ?? 0).toString());
    }
  }, [inventory]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inventory) return;

    const data: { quantity_on_hand: number; safety_stock_level?: number } = {
      quantity_on_hand: parseInt(currentStock, 10),
    };

    if (safetyStock !== (inventory.safety_stock_level ?? inventory.safety_stock ?? 0).toString()) {
      data.safety_stock_level = parseInt(safetyStock, 10);
    }

    onUpdate(inventory.id, data);
  };

  if (!inventory) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Cập nhật Tồn kho">
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Supply Info */}
        <div className="p-3 bg-neutral-50 rounded-lg">
          <div className="text-sm font-medium text-neutral-900">{inventory.supply.name}</div>
          <div className="text-xs text-neutral-500 mt-1">
            Danh mục: {inventory.supply.category} • Đơn vị: {inventory.supply.unit}
          </div>
        </div>

        {/* Current Stock */}
        <div>
          <label htmlFor="current-stock" className="block text-sm font-medium text-neutral-700 mb-1">
            Số lượng hiện tại <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            id="current-stock"
            value={currentStock}
            onChange={(e) => setCurrentStock(e.target.value)}
            min="0"
            required
            className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <p className="text-xs text-neutral-500 mt-1">
            Hiện tại: {inventory.quantity_on_hand} {inventory.supply.unit}
          </p>
        </div>

        {/* Safety Stock */}
        <div>
          <label htmlFor="safety-stock" className="block text-sm font-medium text-neutral-700 mb-1">
            Mức tồn kho an toàn
          </label>
          <input
            type="number"
            id="safety-stock"
            value={safetyStock}
            onChange={(e) => setSafetyStock(e.target.value)}
            min="0"
            className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <p className="text-xs text-neutral-500 mt-1">
            Hiện tại: {inventory.safety_stock_level} {inventory.supply.unit}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-neutral-200">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isLoading}>
            Hủy
          </Button>
          <Button type="submit" disabled={isLoading}>
            {isLoading ? 'Đang cập nhật...' : 'Cập nhật'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
