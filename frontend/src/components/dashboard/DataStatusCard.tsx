import { AlertTriangle, CheckCircle2, Database, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useRunSync, useSyncStatus } from '../../hooks/useSync';
import { ROUTES } from '../../utils/constants';
import { cn } from '../../utils/cn';
import type { DataStatusSection } from '../../types/dashboardV2';

const TABLE_LABELS: Record<string, string> = {
  fact_usage_total: 'Tiêu hao toàn viện',
  fact_cases_by_care_level: 'Ca theo phân cấp',
  fact_usage_by_care_level: 'Tiêu hao theo phân cấp',
  fact_inventory_lot: 'Tồn kho theo lô',
};

function fmtDate(s?: string | null) {
  if (!s) return '—';
  const d = new Date(s.replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/**
 * Thay cho "bản đồ dịch tễ" ở bản gợi ý: người vận hành cần biết dữ liệu
 * đang đứng ở đâu (PROD→STA đẩy lúc nào, app nạp lúc nào, FEFO phủ bao
 * nhiêu mã) hơn là một bản đồ mà hệ thống chỉ có một cơ sở.
 */
export default function DataStatusCard({ status }: { status: DataStatusSection }) {
  const navigate = useNavigate();
  const { data: sync, isLoading } = useSyncStatus();
  const runSync = useRunSync();
  const sta = sync?.sta;
  const warn = sta?.warning ?? null;
  const fefoPct = status.fefo.total ? Math.round((100 * status.fefo.codes) / status.fefo.total) : 0;

  return (
    <div className="space-y-3 text-[12.5px]">
      <Row
        icon={<Database className="w-3.5 h-3.5" />}
        label="Đồng bộ HIS gần nhất"
        value={status.last_sync ? `${fmtDate(status.last_sync.run_at)} · kỳ ${status.last_sync.last_period ?? '—'}` : 'Chưa đồng bộ'}
        ok={status.last_sync?.status === 'ok'}
      />
      <Row
        icon={isLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : warn ? <AlertTriangle className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
        label="PROD → STA"
        value={
          isLoading
            ? 'đang đọc MF_Watermark…'
            : !sta?.available
              ? 'không kết nối được STA'
              : warn
                ? warn
                : sta.last_pushes?.[0]
                  ? `OK · ${fmtDate(sta.last_pushes[0].KetThuc ?? sta.last_pushes[0].BatDau)}`
                  : 'chưa có nhật ký'
        }
        ok={!isLoading && !!sta?.available && !warn}
        warn={!!warn || (!isLoading && !sta?.available)}
      />

      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 pt-1 border-t border-neutral-100">
        {Object.entries(status.dss_tables).map(([t, v]) => (
          <div key={t} className="flex items-baseline justify-between gap-2">
            <span className="text-neutral-600 truncate">{TABLE_LABELS[t] ?? t}</span>
            <span className={cn('tabular-nums font-medium whitespace-nowrap', v ? 'text-neutral-900' : 'text-red-700')}>
              {v ? `${v.rows.toLocaleString('vi-VN')} · ${v.latest ?? '—'}` : 'thiếu'}
            </span>
          </div>
        ))}
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-neutral-600">FEFO áp dụng</span>
          <span className="tabular-nums font-medium text-neutral-900">
            {status.fefo.codes.toLocaleString('vi-VN')}/{status.fefo.total.toLocaleString('vi-VN')} mã · {fefoPct}%
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={() => runSync.mutate()}
          disabled={runSync.isPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-100 text-blue-700 text-xs font-medium hover:bg-blue-100 disabled:opacity-60"
        >
          <RefreshCw className={cn('w-3.5 h-3.5', runSync.isPending && 'animate-spin')} />
          {runSync.isPending ? 'Đang đồng bộ…' : 'Đồng bộ HIS'}
        </button>
        <button
          type="button"
          onClick={() => navigate(ROUTES.SETTINGS)}
          className="text-xs text-neutral-500 hover:text-neutral-800 hover:underline"
        >
          Cấu hình kết nối
        </button>
        {runSync.isError && <span className="text-xs text-red-700">Đồng bộ thất bại</span>}
      </div>
    </div>
  );
}

function Row({
  icon,
  label,
  value,
  ok,
  warn,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  ok?: boolean;
  warn?: boolean;
}) {
  return (
    <div className="flex items-start gap-2">
      <span className={cn('mt-0.5', warn ? 'text-amber-600' : ok ? 'text-emerald-600' : 'text-neutral-400')}>{icon}</span>
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-neutral-500 font-semibold">{label}</div>
        <div className={cn('leading-snug', warn ? 'text-amber-800' : 'text-neutral-800')}>{value}</div>
      </div>
    </div>
  );
}
