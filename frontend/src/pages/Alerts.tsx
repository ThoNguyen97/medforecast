import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, RefreshCw, Search } from 'lucide-react';

import { useUIStore } from '../store/uiStore';
import { useAuthStore } from '../store/authStore';
import { dssService } from '../services/dssService';
import { cn } from '../utils/cn';
import KpiTile from '../components/dashboard/KpiTile';
import LevelPill from '../components/dashboard/LevelPill';
import {
  BLOCK_LABELS,
  GREY_REASON_LABELS,
  LEVEL_LABELS,
  type AlertLevel,
  type AlertRow,
} from '../types/dashboardV2';

const PAGE_SIZE = 25;

const fmt = (v: number | null | undefined, digits = 0) =>
  v == null ? '—' : v.toLocaleString('vi-VN', { maximumFractionDigits: digits });

/**
 * Cảnh báo thiếu hụt — 12/09/2026.
 *
 * Trang này và Tổng quan đọc CÙNG một chuỗi Tầng 1 → 2 → 3
 * (/dashboard/v2/alerts): cùng dự báo Ŷ_g, cùng định mức thực nghiệm, cùng
 * ngưỡng `dss.thresholds`. Khác biệt duy nhất: ở đây trả mọi dòng, phân trang
 * server, có tìm kiếm và lọc danh mục. Không có cột "đề xuất nhập" — phạm vi
 * dừng ở cảnh báo; Δ_need = max(0, nhu cầu horizon − tồn hữu dụng) là mức
 * thiếu hụt dự kiến, không phải lượng mua.
 *
 * Trước 12/09 trang này gọi supply_recommendation_service (định mức nhập tay
 * × tỷ lệ Nhẹ/TB/Nặng, ngưỡng 3/7/14) nên ra con số khác Dashboard.
 */
export default function Alerts() {
  const { setPageTitle } = useUIStore();
  const { isAuthenticated } = useAuthStore();
  useEffect(() => setPageTitle('Cảnh báo thiếu hụt'), [setPageTitle]);

  const [focus, setFocus] = useState(true);
  const [level, setLevel] = useState<AlertLevel | null>(null);
  const [danhMuc, setDanhMuc] = useState('');
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);

  // gõ xong 300ms mới gọi server
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => setPage(1), [focus, level, danhMuc, q]);

  const query = useQuery({
    queryKey: ['dss', 'alerts', focus, level ?? 'all', danhMuc, q, page],
    queryFn: () =>
      dssService.getAlerts({
        focus,
        level,
        q: q || undefined,
        danh_muc: danhMuc || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
    enabled: isAuthenticated,
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
    placeholderData: (prev) => prev,
  });
  const data = query.data;
  const counts = data?.counts;
  const th = data?.meta.thresholds;
  const horizon = data?.meta.horizon_days ?? 30;
  const demandReady = !!data?.demand.ready;
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  const forecastLine = useMemo(() => {
    if (!data?.forecast.ready) return null;
    const parts = data.forecast.blocks.map((b) => `${BLOCK_LABELS[b.block]} ${fmt(b.point)}`);
    return `${fmt(data.forecast.total.point)} ca · ${parts.join(' · ')}`;
  }, [data]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">Cảnh báo thiếu hụt</h2>
          <p className="text-sm text-neutral-500 mt-1">
            {data?.basis ?? 'DOI = tồn hữu dụng (FEFO) ÷ nhu cầu/ngày'} · nhu cầu dự báo quy về{' '}
            {horizon} ngày
            {data?.meta.forecast_period ? ` · kỳ dự báo ${data.meta.forecast_period}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => query.refetch()}
          disabled={query.isFetching}
          className="inline-flex items-center gap-2 h-9 px-3 rounded-lg border border-neutral-200 bg-white text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
        >
          {query.isFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          Làm mới
        </button>
      </div>

      {/* Cảnh báo hệ thống */}
      {!!data?.canh_bao.length && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 space-y-1">
          {data.canh_bao.map((c, i) => (
            <p key={i}>{c}</p>
          ))}
        </div>
      )}
      {query.error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Không tải được cảnh báo: {(query.error as Error).message}
        </div>
      )}

      {/* KPI */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KpiTile
          label="Đỏ"
          tone="red"
          loading={!data}
          value={fmt(counts?.red)}
          unit="mã"
          context={th ? `DOI ≤ ${fmt(th.red_days)} ngày` : undefined}
          footer="Cần xử lý ngay"
        />
        <KpiTile
          label="Vàng"
          tone="amber"
          loading={!data}
          value={fmt(counts?.amber)}
          unit="mã"
          context={th ? `${fmt(th.red_days)} < DOI ≤ ${fmt(th.amber_days)} ngày` : undefined}
          footer="Đưa vào kỳ bổ sung kế tiếp"
        />
        <KpiTile
          label="Xanh"
          tone="green"
          loading={!data}
          value={fmt(counts?.green)}
          unit="mã"
          context={th ? `DOI > ${fmt(th.amber_days)} ngày` : undefined}
          footer="Theo dõi định kỳ"
        />
        <KpiTile
          label="Xám"
          tone="neutral"
          loading={!data}
          value={fmt(counts?.grey)}
          unit="mã"
          context="Chưa đo được — không phải an toàn"
          footer={
            counts?.ly_do_xam
              ? Object.entries(counts.ly_do_xam)
                  .map(([k, n]) => `${GREY_REASON_LABELS[k as keyof typeof GREY_REASON_LABELS] ?? k}: ${n}`)
                  .join(' · ')
              : undefined
          }
        />
        <KpiTile
          label="Dự báo kỳ tới"
          tone="blue"
          loading={!data}
          value={data?.forecast.ready ? fmt(data.forecast.total.point) : '—'}
          unit={data?.forecast.ready ? 'ca' : undefined}
          context={forecastLine ?? 'Chưa có dự báo — Tầng 2 chưa chạy, cột thiếu hụt để trống'}
          footer={
            data?.demand.ready
              ? `Định mức thực nghiệm · ${fmt(data.demand.so_ma)} mã có nhu cầu`
              : data?.demand.error
                ? `Tầng 2 lỗi: ${data.demand.error}`
                : undefined
          }
        />
      </div>

      {/* Bộ lọc + bảng */}
      <div className="bg-white rounded-2xl border border-neutral-200">
        <div className="px-5 py-4 border-b border-neutral-100 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[220px] max-w-md">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
            <input
              id="alerts-search"
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo mã, tên hoạt chất…"
              className="w-full h-9 pl-9 pr-3 rounded-lg border border-neutral-200 bg-neutral-50 text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            />
          </div>
          <select
            id="alerts-focus"
            value={focus ? 'focus' : 'all'}
            onChange={(e) => setFocus(e.target.value === 'focus')}
            className="h-9 px-3 rounded-lg border border-neutral-200 bg-white text-sm text-neutral-700"
          >
            <option value="focus">Tập trọng tâm hô hấp</option>
            <option value="all">Toàn danh mục</option>
          </select>
          <select
            id="alerts-danhmuc"
            value={danhMuc}
            onChange={(e) => setDanhMuc(e.target.value)}
            className="h-9 px-3 rounded-lg border border-neutral-200 bg-white text-sm text-neutral-700"
          >
            <option value="">Mọi danh mục</option>
            {(data?.danh_muc ?? []).map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-1">
            {([null, 'red', 'amber', 'green', 'grey'] as Array<AlertLevel | null>).map((lv) => (
              <button
                key={lv ?? 'all'}
                type="button"
                onClick={() => setLevel(lv)}
                className={cn(
                  'px-2.5 h-8 rounded-lg text-xs font-medium border transition',
                  level === lv
                    ? 'bg-neutral-900 text-white border-neutral-900'
                    : 'bg-white text-neutral-600 border-neutral-200 hover:bg-neutral-50',
                )}
              >
                {lv ? LEVEL_LABELS[lv] : 'Tất cả'}
                {lv && counts ? ` · ${counts[lv]}` : ''}
              </button>
            ))}
          </div>
        </div>

        <AlertsFullTable rows={data?.rows ?? []} loading={!data} demandReady={demandReady} horizonDays={horizon} />

        <div className="px-5 py-3 border-t border-neutral-100 flex flex-wrap items-center justify-between gap-2 text-xs text-neutral-500">
          <span>
            {data ? `${fmt(data.total)} mã khớp bộ lọc · ${fmt(counts?.total)} mã trong tập` : '…'}
            {data?.meta.assumptions_note ? ` · ${data.meta.assumptions_note}` : ''}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="h-8 px-3 rounded-lg border border-neutral-200 bg-white disabled:opacity-40"
            >
              Trước
            </button>
            <span className="tabular-nums">
              {page} / {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="h-8 px-3 rounded-lg border border-neutral-200 bg-white disabled:opacity-40"
            >
              Sau
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertsFullTable({
  rows,
  loading,
  demandReady,
  horizonDays,
}: {
  rows: AlertRow[];
  loading: boolean;
  demandReady: boolean;
  horizonDays: number;
}) {
  if (loading) {
    return (
      <div className="px-5 py-5 space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-9 rounded bg-neutral-100 animate-pulse" />
        ))}
      </div>
    );
  }
  if (rows.length === 0) {
    return <div className="py-12 text-center text-sm text-neutral-400">Không có mã nào khớp bộ lọc.</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-neutral-500 text-[11px] uppercase tracking-wide">
            <th className="text-left px-5 py-2.5 font-semibold">Vật tư</th>
            <th className="text-left px-3 py-2.5 font-semibold">Danh mục</th>
            <th className="text-right px-3 py-2.5 font-semibold" title="Tổng tồn theo lô">Tồn</th>
            <th className="text-right px-3 py-2.5 font-semibold" title="Tồn sau khi trừ lô sắp hết hạn (FEFO)">Hữu dụng</th>
            <th className="text-right px-3 py-2.5 font-semibold" title="Mẫu số: tiêu hao trung bình 12 kỳ">Nhu cầu/ngày</th>
            <th className="text-right px-3 py-2.5 font-semibold" title={`Nhu cầu dự báo ${horizonDays} ngày = Σ Ŷ·p̂·Norm + nền`}>
              Nhu cầu {horizonDays}ng
            </th>
            <th className="text-right px-3 py-2.5 font-semibold" title="Days of Inventory = hữu dụng ÷ nhu cầu/ngày">DOI</th>
            <th className="text-right px-3 py-2.5 font-semibold" title={`Δ = max(0, nhu cầu ${horizonDays} ngày − hữu dụng)`}>
              Thiếu hụt
            </th>
            <th className="text-left px-5 py-2.5 font-semibold">Mức</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.supply_code} className="border-t border-neutral-100 hover:bg-neutral-50">
              <td className="px-5 py-2.5">
                <div className="font-medium text-neutral-900 leading-tight">{r.ten}</div>
                <div className="text-[11px] text-neutral-500 font-mono">
                  {r.supply_code}
                  {r.don_vi ? ` · ${r.don_vi}` : ''}
                  {r.ty_trong_hohap != null ? ` · hô hấp ${fmt(r.ty_trong_hohap, 0)}%` : ''}
                  {r.fefo_ap_dung ? '' : ' · chưa FEFO'}
                </div>
              </td>
              <td className="px-3 py-2.5 text-neutral-600">{r.danh_muc}</td>
              <td className="px-3 py-2.5 text-right tabular-nums text-neutral-600">{fmt(r.s_total)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {fmt(r.s_usable)}
                {r.s_expiring > 0 && (
                  <span className="block text-[10px] text-amber-700">−{fmt(r.s_expiring)} sắp hết hạn</span>
                )}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums text-neutral-600">{fmt(r.d_daily, 2)}</td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {!demandReady ? <span className="text-neutral-400">đang tính</span> : fmt(r.d_forecast, 1)}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums font-semibold whitespace-nowrap">
                {r.doi == null ? '—' : `${fmt(r.doi, 1)} ng`}
              </td>
              <td className="px-3 py-2.5 text-right tabular-nums">
                {!demandReady ? (
                  <span className="text-neutral-400">—</span>
                ) : r.delta_need == null ? (
                  '—'
                ) : r.delta_need > 0 ? (
                  <span className="text-red-700 font-semibold">{fmt(r.delta_need)}</span>
                ) : (
                  <span className="text-neutral-400">0</span>
                )}
              </td>
              <td className="px-5 py-2.5">
                <LevelPill
                  level={r.muc}
                  label={r.muc === 'grey' && r.ly_do_xam ? GREY_REASON_LABELS[r.ly_do_xam] : undefined}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
