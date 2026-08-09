import { useState } from 'react';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn';
import { REPORT_TYPES, type ReportKind } from './ReportTypePicker';

interface PreviewMetric {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'success' | 'warning' | 'danger';
}

interface PreviewSection {
  title: string;
  rows: Array<Record<string, string | number>>;
  columns: { key: string; label: string; align?: 'left' | 'right' }[];
}

interface Props {
  kind: ReportKind;
  isLoading?: boolean;
  isEmpty?: boolean;
  metrics?: PreviewMetric[];
  sections?: PreviewSection[];
  generatedAt?: string;
  periodLabel?: string;
  filtersLabel?: string;
}

export default function ReportPreview({
  kind,
  isLoading,
  isEmpty,
  metrics,
  sections,
  generatedAt,
  periodLabel,
  filtersLabel,
}: Props) {
  const meta = REPORT_TYPES.find((t) => t.key === kind)!;

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      {/* Document header */}
      <div className="px-6 py-5 border-b border-neutral-100">
        <p className="text-[11px] font-semibold tracking-wider uppercase text-blue-600">
          Báo cáo
        </p>
        <h3 className="text-xl font-bold text-neutral-900 mt-1">
          {meta.title}
        </h3>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-neutral-500 mt-1.5">
          {periodLabel && <span>Kỳ báo cáo: {periodLabel}</span>}
          {filtersLabel && <span>Phạm vi: {filtersLabel}</span>}
          {generatedAt && <span>Cập nhật: {generatedAt}</span>}
        </div>
      </div>

      {/* Body */}
      {isLoading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-neutral-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          Đang tổng hợp dữ liệu...
        </div>
      ) : isEmpty ? (
        <div className="py-16 text-center text-sm text-neutral-400">
          Không có dữ liệu trong khoảng thời gian đã chọn.
        </div>
      ) : (
        <div className="p-6 space-y-6">
          {metrics && metrics.length > 0 && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {metrics.map((m) => (
                <MetricBlock key={m.label} {...m} />
              ))}
            </div>
          )}

          {sections?.map((s) => (
            <PreviewTable key={s.title} section={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function MetricBlock({ label, value, hint, tone = 'default' }: PreviewMetric) {
  const valueColor =
    tone === 'success'
      ? 'text-emerald-700'
      : tone === 'warning'
      ? 'text-amber-700'
      : tone === 'danger'
      ? 'text-red-600'
      : 'text-neutral-900';
  return (
    <div className="rounded-xl border border-neutral-200 bg-neutral-50/60 px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <p className={cn('text-2xl font-extrabold tabular-nums mt-1', valueColor)}>
        {value}
      </p>
      {hint && <p className="text-[11px] text-neutral-400 mt-0.5">{hint}</p>}
    </div>
  );
}

const ROWS_PER_PAGE = 10;

function PreviewTable({ section }: { section: PreviewSection }) {
  const [page, setPage] = useState(1);
  const total = section.rows.length;
  const totalPages = Math.max(1, Math.ceil(total / ROWS_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * ROWS_PER_PAGE;
  const pageRows = section.rows.slice(start, start + ROWS_PER_PAGE);

  return (
    <div>
      <h4 className="text-sm font-semibold text-neutral-900 mb-2">
        {section.title}
      </h4>
      <div className="overflow-x-auto rounded-xl border border-neutral-100">
        <table className="w-full text-sm">
          <thead className="bg-neutral-50">
            <tr className="text-[11px] uppercase tracking-wider text-neutral-500">
              {section.columns.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    'px-4 py-2.5 font-semibold',
                    c.align === 'right' ? 'text-right' : 'text-left',
                  )}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {total === 0 ? (
              <tr>
                <td
                  colSpan={section.columns.length}
                  className="py-6 text-center text-sm text-neutral-400"
                >
                  Không có dữ liệu
                </td>
              </tr>
            ) : (
              pageRows.map((row, idx) => (
                <tr key={start + idx} className="border-t border-neutral-100">
                  {section.columns.map((c) => (
                    <td
                      key={c.key}
                      className={cn(
                        'px-4 py-2.5 text-neutral-700',
                        c.align === 'right' && 'text-right tabular-nums',
                      )}
                    >
                      {row[c.key] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {total > ROWS_PER_PAGE && (
        <div className="flex flex-wrap items-center justify-between gap-3 mt-3 text-sm text-neutral-500">
          <span className="text-xs">
            Hiển thị {start + 1}-{Math.min(start + ROWS_PER_PAGE, total)} trong số{' '}
            {total.toLocaleString('vi-VN')} dòng
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage <= 1}
              className="p-1.5 border border-neutral-200 rounded-md disabled:opacity-30 hover:bg-neutral-50"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            {Array.from({ length: Math.min(totalPages, 5) }).map((_, i) => {
              let pageNum: number;
              if (totalPages <= 5) pageNum = i + 1;
              else if (safePage <= 3) pageNum = i + 1;
              else if (safePage >= totalPages - 2) pageNum = totalPages - 4 + i;
              else pageNum = safePage - 2 + i;
              return (
                <button
                  key={pageNum}
                  type="button"
                  onClick={() => setPage(pageNum)}
                  className={cn(
                    'w-8 h-8 rounded-md text-sm font-medium',
                    safePage === pageNum
                      ? 'bg-blue-600 text-white'
                      : 'border border-neutral-200 text-neutral-600 hover:bg-neutral-50',
                  )}
                >
                  {pageNum}
                </button>
              );
            })}
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage >= totalPages}
              className="p-1.5 border border-neutral-200 rounded-md disabled:opacity-30 hover:bg-neutral-50"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
