import { Loader2, Edit2, Trash2 } from 'lucide-react';
import { cn } from '../../utils/cn';
import LevelPill from '../dashboard/LevelPill';
import { GREY_REASON_LABELS, type AlertLevel, type GreyReason } from '../../types/dashboardV2';

/**
 * Một dòng thuốc trên trang Quản lý thuốc = danh mục (`/inventory`, có id để
 * sửa/xoá) ghép với dòng DOI cùng `supply_code` từ `/dashboard/v2/alerts`
 * (toàn danh mục). `level = null` nghĩa là mã không có tiêu hao trong 12 kỳ đã
 * chốt → không có mẫu số, không đo được DOI; khác với Xám (có tiêu hao nhưng
 * không có dòng tồn kho).
 */
export interface InventoryRow {
  id: number;
  code: string;
  name: string;
  category: string;
  group: string;
  unit: string;
  currentStock: number;
  usableStock: number | null;
  dDaily: number | null;
  doi: number | null;
  level: AlertLevel | null;
  greyReason: GreyReason | null;
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
}

const fmt = (v: number | null | undefined, digits = 0) =>
  v == null ? '—' : v.toLocaleString('vi-VN', { maximumFractionDigits: digits });

export default function InventoryTable({
  rows,
  isLoading,
  total,
  page,
  pageSize,
  onPageChange,
  onEdit,
  onDelete,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  const colSpan = 10;

  return (
    <div className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-y border-neutral-100">
              <th className="text-left px-4 py-3 font-semibold">Mã</th>
              <th className="text-left px-4 py-3 font-semibold">Hoạt chất</th>
              <th className="text-left px-4 py-3 font-semibold">Danh mục</th>
              <th className="text-left px-4 py-3 font-semibold">ĐVT</th>
              <th className="text-right px-4 py-3 font-semibold">Tồn kho</th>
              <th className="text-right px-4 py-3 font-semibold">Tồn hữu dụng</th>
              <th className="text-right px-4 py-3 font-semibold">Tiêu hao/ngày</th>
              <th className="text-right px-4 py-3 font-semibold">DOI (ngày)</th>
              <th className="text-left px-4 py-3 font-semibold">Nhãn</th>
              <th className="text-center px-4 py-3 font-semibold">Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={colSpan} className="py-10">
                  <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Đang tải danh mục thuốc...
                  </div>
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={colSpan} className="py-10 text-center text-sm text-neutral-400">
                  Không có thuốc nào khớp bộ lọc
                </td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr key={r.id} className="border-t border-neutral-100 hover:bg-neutral-50/60">
                  <td className="px-4 py-3 text-neutral-700 font-medium whitespace-nowrap">{r.code}</td>
                  <td className="px-4 py-3">
                    <div className="text-neutral-900 font-semibold">{r.name}</div>
                    {r.group && r.group !== r.category && (
                      <div className="text-xs text-neutral-500 mt-0.5">{r.group}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-neutral-700 whitespace-nowrap">{r.category}</td>
                  <td className="px-4 py-3 text-neutral-700">{r.unit}</td>
                  <td className={cn('px-4 py-3 text-right font-semibold tabular-nums', stockColor(r.level))}>
                    {fmt(r.currentStock)}
                  </td>
                  <td className="px-4 py-3 text-right text-neutral-700 tabular-nums">{fmt(r.usableStock)}</td>
                  <td className="px-4 py-3 text-right text-neutral-700 tabular-nums">{fmt(r.dDaily, 2)}</td>
                  <td className="px-4 py-3 text-right text-neutral-900 font-semibold tabular-nums">{fmt(r.doi, 1)}</td>
                  <td className="px-4 py-3">
                    {r.level ? (
                      <span className="inline-flex flex-col gap-0.5">
                        <LevelPill level={r.level} />
                        {r.level === 'grey' && r.greyReason && (
                          <span className="text-[11px] text-neutral-500">{GREY_REASON_LABELS[r.greyReason]}</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-[11px] text-neutral-400 whitespace-nowrap">Không tiêu hao 12 kỳ</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-2">
                      {onEdit && (
                        <button
                          onClick={() => onEdit(r)}
                          className="p-1.5 rounded-lg hover:bg-blue-50 text-blue-600 transition-colors"
                          title="Sửa tồn kho đầu kỳ"
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
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-t border-neutral-100 text-sm text-neutral-600">
        <span>
          Hiển thị <span className="font-medium text-neutral-700">{start}-{end}</span> của{' '}
          <span className="font-medium text-neutral-700">{total.toLocaleString('vi-VN')}</span> mã
        </span>
        <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />
      </div>
    </div>
  );
}

function stockColor(level: AlertLevel | null) {
  if (level === 'red') return 'text-red-600';
  if (level === 'amber') return 'text-amber-600';
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
          <span key={`e-${idx}`} className="w-8 h-8 inline-flex items-center justify-center text-neutral-400">
            …
          </span>
        ) : (
          <PaginationButton key={p} active={p === page} onClick={() => onPageChange(p)}>
            {p}
          </PaginationButton>
        ),
      )}
      <PaginationButton onClick={() => onPageChange(page + 1)} disabled={page >= totalPages}>
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
        active ? 'bg-blue-600 text-white' : 'bg-white text-neutral-600 hover:bg-neutral-50 border border-neutral-200',
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
