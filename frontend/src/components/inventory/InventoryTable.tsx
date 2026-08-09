import { Loader2, Edit2, Trash2 } from 'lucide-react';
import { cn } from '../../utils/cn';
import InventoryStatusBadge, {
  classifyStatus,
  type InventoryStatus,
} from './InventoryStatusBadge';
import type { SeverityLevel } from './InventoryToolbar';

export interface InventoryRow {
  id: number;
  code: string;
  name: string;
  category: string;
  unit: string;
  currentStock: number;
  safetyStock: number;
  /** Định mức theo bệnh đang chọn (undefined = chưa có dữ liệu) */
  mild?: number;
  moderate?: number;
  severe?: number;
}

interface Props {
  rows: InventoryRow[];
  isLoading?: boolean;
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onEdit?: (row: InventoryRow) => void;
  onDelete?: (row: InventoryRow) => void;
  /** Hiện cột định mức khi đã chọn bệnh */
  showSeverity?: boolean;
  /** Cấp độ đang chọn: 'all' hiện đủ 3 cột, ngược lại chỉ hiện 1 cột tương ứng */
  level?: SeverityLevel;
}

export default function InventoryTable({
  rows,
  isLoading,
  total,
  page,
  pageSize,
  onPageChange,
  onEdit,
  onDelete,
  showSeverity = false,
  level = 'all',
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  const showMild = showSeverity && (level === 'all' || level === 'mild');
  const showModerate = showSeverity && (level === 'all' || level === 'moderate');
  const showSevere = showSeverity && (level === 'all' || level === 'severe');
  const severityCols = [showMild, showModerate, showSevere].filter(Boolean).length;
  const colSpan = 8 + severityCols;

  return (
    <div className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-y border-neutral-100">
              <th className="text-left px-5 py-3 font-semibold">Mã VT</th>
              <th className="text-left px-5 py-3 font-semibold">Tên vật tư</th>
              <th className="text-left px-5 py-3 font-semibold">Loại</th>
              <th className="text-left px-5 py-3 font-semibold">ĐVT</th>
              <th className="text-right px-5 py-3 font-semibold">Tồn kho</th>
              <th className="text-right px-5 py-3 font-semibold">Ngưỡng AT</th>
              {showMild && (
                <th className="text-center px-3 py-3 font-semibold">
                  <span className="inline-flex items-center px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded text-[10px]">Nhẹ</span>
                </th>
              )}
              {showModerate && (
                <th className="text-center px-3 py-3 font-semibold">
                  <span className="inline-flex items-center px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px]">TB</span>
                </th>
              )}
              {showSevere && (
                <th className="text-center px-3 py-3 font-semibold">
                  <span className="inline-flex items-center px-2 py-0.5 bg-red-100 text-red-700 rounded text-[10px]">Nặng</span>
                </th>
              )}
              <th className="text-left px-5 py-3 font-semibold">Trạng thái</th>
              <th className="text-center px-5 py-3 font-semibold">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={colSpan} className="py-10">
                  <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tải dữ liệu vật tư...
                  </div>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={colSpan} className="py-10 text-center text-sm text-neutral-400">
                  Không tìm thấy vật tư nào
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const status = classifyStatus(r.currentStock, r.safetyStock);
                return (
                  <tr
                    key={r.id}
                    className="border-t border-neutral-100 hover:bg-neutral-50/60"
                  >
                    <td className="px-5 py-3.5 text-neutral-700 font-medium">
                      {r.code}
                    </td>
                    <td className="px-5 py-3.5 text-neutral-900 font-semibold">
                      {r.name}
                    </td>
                    <td className="px-5 py-3.5 text-neutral-700">{r.category}</td>
                    <td className="px-5 py-3.5 text-neutral-700">{r.unit}</td>
                    <td
                      className={cn(
                        'px-5 py-3.5 text-right font-semibold tabular-nums',
                        stockColor(status),
                      )}
                    >
                      {r.currentStock.toLocaleString('vi-VN')}
                    </td>
                    <td className="px-5 py-3.5 text-right text-neutral-700 tabular-nums">
                      {r.safetyStock.toLocaleString('vi-VN')}
                    </td>
                    {showMild && (
                      <td className="px-3 py-3.5 text-center">
                        <span className="inline-block px-2 py-0.5 bg-emerald-100 text-emerald-900 font-semibold rounded text-xs tabular-nums">
                          {r.mild ?? 0}
                        </span>
                      </td>
                    )}
                    {showModerate && (
                      <td className="px-3 py-3.5 text-center">
                        <span className="inline-block px-2 py-0.5 bg-amber-100 text-amber-900 font-semibold rounded text-xs tabular-nums">
                          {r.moderate ?? 0}
                        </span>
                      </td>
                    )}
                    {showSevere && (
                      <td className="px-3 py-3.5 text-center">
                        <span className="inline-block px-2 py-0.5 bg-red-100 text-red-900 font-semibold rounded text-xs tabular-nums">
                          {r.severe ?? 0}
                        </span>
                      </td>
                    )}
                    <td className="px-5 py-3.5">
                      <InventoryStatusBadge status={status} />
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center justify-center gap-2">
                        {onEdit && (
                          <button
                            onClick={() => onEdit(r)}
                            className="p-1.5 rounded-lg hover:bg-blue-50 text-blue-600 transition-colors"
                            title="Sửa"
                          >
                            <Edit2 className="w-4 h-4" />
                          </button>
                        )}
                        {onDelete && (
                          <button
                            onClick={() => onDelete(r)}
                            className="p-1.5 rounded-lg hover:bg-red-50 text-red-600 transition-colors"
                            title="Xoá"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-t border-neutral-100 text-sm text-neutral-600">
        <span>
          Hiển thị <span className="font-medium text-neutral-700">{start}-{end}</span> của{' '}
          <span className="font-medium text-neutral-700">
            {total.toLocaleString('vi-VN')}
          </span>{' '}
          mục
        </span>
        <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />
      </div>
    </div>
  );
}

function stockColor(status: InventoryStatus) {
  if (status === 'critical') return 'text-red-600';
  if (status === 'low') return 'text-amber-600';
  return 'text-neutral-700';
}

function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;

  const visible = buildPages(page, totalPages);

  return (
    <nav className="inline-flex items-center gap-1">
      <PaginationButton onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
        ‹
      </PaginationButton>
      {visible.map((p, idx) =>
        p === 'ellipsis' ? (
          <span
            key={`e-${idx}`}
            className="w-8 h-8 inline-flex items-center justify-center text-neutral-400"
          >
            …
          </span>
        ) : (
          <PaginationButton
            key={p}
            active={p === page}
            onClick={() => onPageChange(p)}
          >
            {p}
          </PaginationButton>
        ),
      )}
      <PaginationButton
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
      >
        ›
      </PaginationButton>
    </nav>
  );
}

function PaginationButton({
  active,
  disabled,
  onClick,
  children,
}: {
  active?: boolean;
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
        'min-w-8 h-8 px-2 inline-flex items-center justify-center rounded-md text-sm font-medium transition',
        active
          ? 'bg-blue-600 text-white'
          : 'bg-white text-neutral-600 hover:bg-neutral-50 border border-neutral-200',
        disabled && 'opacity-40 cursor-not-allowed hover:bg-white',
      )}
    >
      {children}
    </button>
  );
}

function buildPages(current: number, total: number): Array<number | 'ellipsis'> {
  if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: Array<number | 'ellipsis'> = [];
  pages.push(1);
  if (current > 3) pages.push('ellipsis');
  const startWindow = Math.max(2, current - 1);
  const endWindow = Math.min(total - 1, current + 1);
  for (let p = startWindow; p <= endWindow; p++) pages.push(p);
  if (current < total - 2) pages.push('ellipsis');
  pages.push(total);
  return pages;
}
