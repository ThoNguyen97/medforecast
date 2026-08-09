import { useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { useAuditLogs } from '../../hooks/useConfig';
import { cn } from '../../utils/cn';

const ACTION_TONE: Record<string, string> = {
  CREATE: 'bg-emerald-50 text-emerald-700',
  UPDATE: 'bg-blue-50 text-blue-700',
  DELETE: 'bg-red-50 text-red-700',
  LOGIN: 'bg-violet-50 text-violet-700',
  LOGOUT: 'bg-neutral-100 text-neutral-600',
};

export default function AuditLogsSection() {
  const [limit, setLimit] = useState(50);
  const { data: logs = [], isLoading, refetch, isFetching } = useAuditLogs({
    limit,
  });

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-100 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">
            Nhật ký hệ thống
          </h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            Ghi nhận thao tác người dùng: thêm/sửa/xoá, chạy dự báo, xuất báo cáo, đăng nhập...
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="h-9 px-3 rounded-lg border border-neutral-200 bg-white text-sm font-medium text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          >
            <option value={50}>50 dòng gần nhất</option>
            <option value={100}>100 dòng gần nhất</option>
            <option value={200}>200 dòng gần nhất</option>
          </select>
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-lg border border-neutral-200 bg-white text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            <RefreshCw
              className={cn('w-3.5 h-3.5', isFetching && 'animate-spin')}
            />
            Làm mới
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="py-10 flex items-center justify-center gap-2 text-sm text-neutral-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          Đang tải nhật ký...
        </div>
      ) : logs.length === 0 ? (
        <div className="py-10 text-center text-sm text-neutral-400">
          Chưa có nhật ký nào
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-b border-neutral-100">
                <th className="text-left px-5 py-3 font-semibold">Thời gian</th>
                <th className="text-left px-5 py-3 font-semibold">Người thực hiện</th>
                <th className="text-left px-5 py-3 font-semibold">Hành động</th>
                <th className="text-left px-5 py-3 font-semibold">Bảng dữ liệu</th>
                <th className="text-left px-5 py-3 font-semibold">Giá trị mới</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  className="border-t border-neutral-100 hover:bg-neutral-50/60"
                >
                  <td className="px-5 py-2.5 text-neutral-500 whitespace-nowrap">
                    {formatDate(log.created_at)}
                  </td>
                  <td className="px-5 py-2.5 font-medium text-neutral-700">
                    {log.username ?? `User #${log.user_id ?? '?'}`}
                  </td>
                  <td className="px-5 py-2.5">
                    <span
                      className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold',
                        ACTION_TONE[log.action] ??
                          'bg-neutral-100 text-neutral-600',
                      )}
                    >
                      {log.action}
                    </span>
                  </td>
                  <td className="px-5 py-2.5 text-neutral-500">
                    {log.table_name ?? '—'}
                  </td>
                  <td className="px-5 py-2.5 text-neutral-700 font-mono text-xs max-w-[280px] truncate">
                    {formatValue(log.new_value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatDate(iso: string) {
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      dateStyle: 'short',
      timeStyle: 'medium',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function formatValue(val: Record<string, unknown> | null | undefined) {
  if (!val) return '—';
  const str = JSON.stringify(val);
  return str.length > 80 ? str.slice(0, 77) + '...' : str;
}
