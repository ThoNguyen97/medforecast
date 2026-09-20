import { useNavigate } from 'react-router-dom';
import { Loader2, Edit2, Trash2 } from 'lucide-react';
import { cn } from '../../utils/cn';
import { ROUTES } from '../../utils/constants';
import LevelPill from '../dashboard/LevelPill';
import { GREY_REASON_LABELS, type AlertLevel, type GreyReason } from '../../types/dashboardV2';

/**
 * Một dòng thuốc trên trang Danh mục & tồn kho = danh mục (`/inventory`, có id để
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
  dDaily: number | null;          // mẫu số DOI: nhu cầu dự báo mỗi ngày
  dForecast: number | null;       // nhu cầu dự báo cả chân trời
  deltaNeed: number | null;       // thiếu hụt = dForecast − usableStock, không âm
  doi: number | null;
  level: AlertLevel | null;
  greyReason: GreyReason | null;
}

interface Props {
  rows: InventoryRow[];
  isLoading?: boolean;
  /** Chân trời nhu cầu (ngày) — tham số Quản trị, không viết cứng 30. */
  horizonDays: number;
  /** Dòng công thức do backend dựng, dùng chung với trang Cảnh báo thiếu hụt. */
  basis?: string;
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
  horizonDays,
  basis,
  total,
  page,
  pageSize,
  onPageChange,
  onEdit,
  onDelete,
}: Props) {
  const navigate = useNavigate();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  const colSpan = 12;

  return (
    <div className="overflow-hidden">
      {basis && (
        <p className="px-5 pt-4 pb-1 text-xs text-neutral-500">{basis}</p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            {/* Hai hàng tiêu đề: nhóm trái là sổ cái danh mục — việc chính của
                trang này; nhóm phải là số của Tầng 1→2→3, để tham chiếu và
                cũng là số mà trang Cảnh báo thiếu hụt dùng. */}
            <tr className="text-neutral-400 text-[10px] uppercase tracking-wider">
              <th colSpan={4} className="text-left px-4 pt-3 pb-1 font-semibold">Danh mục</th>
              <th colSpan={2} className="text-right px-4 pt-3 pb-1 font-semibold">Tồn kho</th>
              <th colSpan={5} className="text-right px-4 pt-3 pb-1 font-semibold border-l border-neutral-100">
                Dự báo &amp; cảnh báo
              </th>
              <th className="px-4 pt-3 pb-1" />
            </tr>
            <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-y border-neutral-100">
              <th className="text-left px-4 py-3 font-semibold">Mã</th>
              <th className="text-left px-4 py-3 font-semibold">Hoạt chất</th>
              <th className="text-left px-4 py-3 font-semibold">Danh mục</th>
              <th className="text-left px-4 py-3 font-semibold">ĐVT</th>
              <th className="text-right px-4 py-3 font-semibold">Tồn kho</th>
              <th
                className="text-right px-4 py-3 font-semibold"
                title="Phần tồn còn dùng kịp trước hạn, tính theo lô hết hạn sớm trước."
              >
                Tồn hữu dụng
              </th>
              <th
                className="text-right px-4 py-3 font-semibold border-l border-neutral-100"
                title={`Số ca dự báo kỳ tới quy đổi theo định mức tiêu hao thực tế, tính cho ${horizonDays} ngày.`}
              >
                Nhu cầu {horizonDays} ngày
              </th>
              <th className="text-right px-4 py-3 font-semibold" title="Nhu cầu dự báo chia cho chân trời.">
                Nhu cầu/ngày
              </th>
              <th
                className="text-right px-4 py-3 font-semibold"
                title={`Phần nhu cầu ${horizonDays} ngày mà tồn hữu dụng không đáp ứng. Chưa trừ hàng đang về.`}
              >
                Thiếu hụt
              </th>
              <th
                className="text-right px-4 py-3 font-semibold"
                title="Số ngày tồn hữu dụng đủ dùng theo nhu cầu dự báo."
              >
                DOI (ngày)
              </th>
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
                  <td className="px-4 py-3 text-right text-neutral-500 tabular-nums border-l border-neutral-100">
                    {fmt(r.dForecast)}
                  </td>
                  <td className="px-4 py-3 text-right text-neutral-500 tabular-nums">{fmt(r.dDaily, 2)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {r.deltaNeed == null ? (
                      <span className="text-neutral-400">—</span>
                    ) : r.deltaNeed > 0 ? (
                      <span className="text-red-700 font-semibold">{fmt(r.deltaNeed)}</span>
                    ) : (
                      <span className="text-neutral-400">0</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-neutral-600 font-medium tabular-nums">{fmt(r.doi, 1)}</td>
                  <td className="px-4 py-3">
                    {r.level ? (
                      <button
                        type="button"
                        onClick={() =>
                          navigate(`${ROUTES.ALERTS}?focus=all&q=${encodeURIComponent(r.code)}`)
                        }
                        className="inline-flex flex-col gap-0.5 text-left"
                        title="Xem mã này trong Cảnh báo thiếu hụt"
                      >
                        <LevelPill level={r.level} />
                        {r.level === 'grey' && r.greyReason && (
                          <span className="text-[11px] text-neutral-500">{GREY_REASON_LABELS[r.greyReason]}</span>
                        )}
                      </button>
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
