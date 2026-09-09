import { Loader2, MoreVertical } from 'lucide-react';
import { cn } from '../../utils/cn';
import type { StockClass } from './StatusKpiCards';

export interface AlertRow {
  id: number;
  supply_id: number;
  name: string;
  code: string;
  unit: string;
  currentStock: number;
  demand: number;
  recommendedOrder: number;
  status: StockClass;
}

interface Props {
  rows: AlertRow[];
  isLoading?: boolean;
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedIds: Set<number>;
  onToggleRow: (id: number) => void;
  onToggleAll: (checked: boolean) => void;
}

export default function AlertsTable({
  rows,
  isLoading,
  total,
  page,
  pageSize,
  onPageChange,
  selectedIds,
  onToggleRow,
  onToggleAll,
}: Props) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const allChecked = rows.length > 0 && rows.every((r) => selectedIds.has(r.id));

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-y border-neutral-100">
              <th className="text-left px-5 py-3 font-semibold w-10">
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={(e) => onToggleAll(e.target.checked)}
                  className="rounded border-neutral-300"
                />
              </th>
              <th className="text-left px-5 py-3 font-semibold">Tên vật tư / Mã SP</th>
              <th className="text-right px-5 py-3 font-semibold">Tồn hiện tại</th>
              <th className="text-right px-5 py-3 font-semibold">Nhu cầu dự báo (30d)</th>
              <th className="text-left px-5 py-3 font-semibold">Trạng thái</th>
              <th className="text-right px-5 py-3 font-semibold">Đề xuất nhập</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="py-10">
                  <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tính nhu cầu vật tư...
                  </div>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-neutral-400">
                  Không có vật tư phù hợp với bộ lọc
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const checked = selectedIds.has(r.id);
                return (
                  <tr
                    key={r.id}
                    className={cn(
                      'border-t border-neutral-100 transition-colors',
                      checked ? 'bg-blue-50/40' : 'hover:bg-neutral-50/60',
                    )}
                  >
                    <td className="px-5 py-3.5">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onToggleRow(r.id)}
                        className="rounded border-neutral-300"
                      />
                    </td>
                    <td className="px-5 py-3.5">
                      <p className="text-neutral-900 font-semibold leading-tight">
                        {r.name}
                      </p>
                      <p className="text-xs text-neutral-400 mt-0.5">{r.code}</p>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <span
                        className={cn(
                          'block font-semibold tabular-nums',
                          stockColor(r.status),
                        )}
                      >
                        {r.currentStock.toLocaleString('vi-VN')}
                      </span>
                      <span className="block text-[11px] text-neutral-400">
                        {r.unit}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <span className="block text-neutral-700 font-medium tabular-nums">
                        {r.demand.toLocaleString('vi-VN')}
                      </span>
                      <span className="block text-[11px] text-neutral-400">
                        {r.unit}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusPill status={r.status} />
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {r.recommendedOrder > 0 ? (
                        <span className="inline-flex items-center justify-center min-w-[68px] px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 text-sm font-semibold tabular-nums">
                          {r.recommendedOrder.toLocaleString('vi-VN')}
                        </span>
                      ) : (
                        <span className="text-neutral-400 text-sm">0</span>
                      )}
                    </td>
                    <td className="px-2 py-3.5 text-right">
                      <button
                        type="button"
                        className="p-1.5 rounded-md hover:bg-neutral-100 text-neutral-400"
                        aria-label="Hành động khác"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-t border-neutral-100 text-sm text-neutral-600">
        <span>
          Hiển thị{' '}
          <span className="font-medium text-neutral-700">
            {start}-{end}
          </span>{' '}
          của <span className="font-medium text-neutral-700">{total}</span> vật tư
        </span>
        <div className="inline-flex items-center gap-1">
          <PaginationButton onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
            ‹
          </PaginationButton>
          <PaginationButton onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}>
            ›
          </PaginationButton>
        </div>
      </div>
    </div>
  );
}

function stockColor(status: StockClass): string {
  switch (status) {
    case 'critical':
      return 'text-red-600';
    case 'warning':
      return 'text-amber-600';
    case 'safe':
      return 'text-emerald-600';
    case 'overstock':
      return 'text-neutral-700';
  }
}

function StatusPill({ status }: { status: StockClass }) {
  const cfg: Record<StockClass, { label: string; bg: string; text: string; dot: string }> = {
    critical: {
      label: 'NGUY HIỂM',
      bg: 'bg-red-50',
      text: 'text-red-700',
      dot: 'bg-red-500',
    },
    warning: {
      label: 'CẢNH BÁO',
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      dot: 'bg-amber-500',
    },
    safe: {
      label: 'AN TOÀN',
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      dot: 'bg-emerald-500',
    },
    overstock: {
      label: 'DƯ TỒN',
      bg: 'bg-neutral-100',
      text: 'text-neutral-700',
      dot: 'bg-neutral-400',
    },
  };
  const c = cfg[status];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold',
        c.bg,
        c.text,
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', c.dot)} />
      {c.label}
    </span>
  );
}

function PaginationButton({
  disabled,
  onClick,
  children,
}: {
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'min-w-8 h-8 px-2 inline-flex items-center justify-center rounded-md border border-neutral-200',
        'bg-white text-neutral-600 hover:bg-neutral-50 transition',
        disabled && 'opacity-40 cursor-not-allowed hover:bg-white',
      )}
    >
      {children}
    </button>
  );
}
