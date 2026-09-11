import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownRight, ArrowUpRight, Check, Download, Loader2, RefreshCw } from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { useDashboardForecast, useDashboardV2 } from '../hooks/useDashboard';
import { reportsService } from '../services/reportsService';
import { ROUTES } from '../utils/constants';
import { cn } from '../utils/cn';
import KpiTile, { type KpiTone } from '../components/dashboard/KpiTile';
import LevelPill from '../components/dashboard/LevelPill';
import TrendChart from '../components/dashboard/TrendChart';
import DoiCategoryChart from '../components/dashboard/DoiCategoryChart';
import AlertsTable from '../components/dashboard/AlertsTable';
import CareLevelChart from '../components/dashboard/CareLevelChart';
import DataStatusCard from '../components/dashboard/DataStatusCard';
import InsightsCard from '../components/dashboard/InsightsCard';
import DashboardFilters, { type DashboardFilterState } from '../components/dashboard/DashboardFilters';
import { BLOCK_LABELS, type DashboardV2 } from '../types/dashboardV2';

const ALERT_LIMIT = 8;

/**
 * Tổng quan — Tuần 3 (11/09/2026).
 *
 * Một payload (/dashboard/v2) dựng toàn bộ trang; dự báo (/dashboard/v2/forecast)
 * tải riêng vì lần đầu phải khớp ensemble. Mọi KPI neo vào KỲ ĐÃ CHỐT gần
 * nhất; kỳ đang mở chỉ hiện với nhãn "chưa chốt". Không có ngôn ngữ mua sắm:
 * cột thiếu hụt là Δ_need = max(0, nhu cầu dự báo − tồn hữu dụng).
 */
export default function Dashboard() {
  const { setPageTitle } = useUIStore();
  const [filters, setFilters] = useState<DashboardFilterState>({ block: 'all', focus: true, level: null });
  const [exporting, setExporting] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);

  const v2 = useDashboardV2({ focus: filters.focus, level: filters.level, limit: ALERT_LIMIT });
  const fc = useDashboardForecast();
  const data = v2.data;

  useEffect(() => {
    setPageTitle('Tổng quan');
  }, [setPageTitle]);

  useEffect(() => {
    if (refreshedAt === null) return;
    const t = setTimeout(() => setRefreshedAt(null), 2500);
    return () => clearTimeout(t);
  }, [refreshedAt]);

  const refreshing = v2.isFetching || fc.isFetching;
  const handleRefresh = async () => {
    if (refreshing) return;
    await Promise.all([v2.refetch(), fc.refetch()]);
    setRefreshedAt(Date.now());
  };

  const handleExport = async () => {
    if (exporting) return;
    try {
      setExporting(true);
      const blob = await reportsService.exportReport({ report_type: 'dashboard-summary' as never });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tong_quan_${new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert('Không thể xuất báo cáo, vui lòng thử lại.');
    } finally {
      setExporting(false);
    }
  };

  const lastUpdated = data?.meta.generated_at
    ? new Date(data.meta.generated_at).toLocaleString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    : '—';

  const kpi = useMemo(() => buildKpis(data, fc.data, fc.isLoading, filters), [data, fc.data, fc.isLoading, filters]);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-extrabold text-neutral-900">Tổng quan</h2>
          <p className="text-sm text-neutral-500 mt-0.5">
            Dữ liệu tính lúc {lastUpdated}
            {data?.meta.assumptions_note && <span className="text-neutral-400"> · {data.meta.assumptions_note}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {refreshedAt !== null && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-50 border border-green-100 rounded-lg text-sm font-medium text-green-700">
              <Check className="w-4 h-4" />
              Đã cập nhật
            </span>
          )}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <RefreshCw className={cn('w-4 h-4', refreshing && 'animate-spin')} />
            {refreshing ? 'Đang tải…' : 'Làm mới'}
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-100 rounded-xl text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-60"
          >
            {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {exporting ? 'Đang xuất…' : 'Xuất báo cáo'}
          </button>
        </div>
      </div>

      {v2.isError && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Không tải được dữ liệu tổng quan: {(v2.error as Error)?.message ?? 'lỗi không rõ'}. Hãy kiểm tra backend
          và đồng bộ HIS.
        </div>
      )}

      <DashboardFilters
        value={filters}
        onChange={setFilters}
        lastClosed={data?.meta.last_closed_period ?? null}
        openPeriod={data?.meta.open_period ?? null}
        focusCount={data?.catalogue.focus ?? 0}
        allCount={data?.risk.all.total ?? data?.catalogue.active ?? 0}
      />

      {/* KPI */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        {kpi.map((k) => (
          <KpiTile key={k.label} {...k} />
        ))}
      </div>

      {/* Xu hướng + DOI */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Card
          className="lg:col-span-7"
          title="Xu hướng ca bệnh theo tháng"
          subtitle={
            filters.block === 'all'
              ? 'Tổng ba khối hô hấp, 12 kỳ gần nhất, kèm dự báo kỳ tới'
              : `${filters.block} · ${BLOCK_LABELS[filters.block]}, 12 kỳ gần nhất`
          }
          right={<Link to={ROUTES.FORECASTING} className="text-xs text-blue-600 hover:underline font-medium">Phân tích</Link>}
        >
          {data ? (
            <TrendChart trend={data.trend} forecast={data.forecast} block={filters.block} />
          ) : (
            <Skeleton className="h-72" />
          )}
        </Card>
        <Card
          className="lg:col-span-5"
          title="Số ngày tồn phủ nhu cầu theo danh mục"
          subtitle={data ? `${data.risk.selected} · DOI = tồn hữu dụng (FEFO) ÷ nhu cầu/ngày` : undefined}
        >
          {data ? <DoiCategoryChart data={data.doi_by_category} thresholds={data.meta.thresholds} /> : <Skeleton className="h-72" />}
        </Card>
      </div>

      {/* Cảnh báo + phân cấp + dữ liệu */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <Card
          className="lg:col-span-7"
          bodyClassName="px-0 pb-2"
          title="Cảnh báo nguy cơ thiếu hụt"
          subtitle={
            data
              ? `${data.risk.selected} · ${filters.level ? `mức ${LEVEL_TEXT[filters.level]}` : 'Đỏ + Vàng'} · ${data.alerts_total_matched.toLocaleString('vi-VN')} mã khớp, hiện ${Math.min(ALERT_LIMIT, data.alerts_total_matched)}`
              : undefined
          }
          right={<Link to={ROUTES.ALERTS} className="text-xs text-blue-600 hover:underline font-medium">Xem tất cả</Link>}
        >
          <AlertsTable
            rows={data?.alerts ?? []}
            demandReady={!!data?.demand.ready}
            horizonDays={data?.meta.horizon_days ?? 30}
            loading={!data}
          />
          {data && data.risk.canh_bao.length > 0 && (
            <ul className="px-5 pt-2 space-y-1 text-[11px] text-neutral-500">
              {data.risk.canh_bao.map((c, i) => (
                <li key={i}>• {c}</li>
              ))}
            </ul>
          )}
        </Card>
        <div className="lg:col-span-5 grid grid-cols-1 gap-5">
          <Card title="Phân cấp chăm sóc theo nhóm bệnh" subtitle="Tỷ trọng p̂(g, rổ) — đầu vào định mức thực nghiệm Tầng 2">
            {data ? <CareLevelChart data={data.care_level} block={filters.block} /> : <Skeleton className="h-40" />}
          </Card>
          <Card title="Trạng thái dữ liệu" subtitle="HIS PROD → STA → app">
            {data ? <DataStatusCard status={data.data_status} /> : <Skeleton className="h-40" />}
          </Card>
        </div>
      </div>

      <Card title="Diễn giải nhanh" subtitle="Sinh từ chính các con số trên màn hình">
        {data ? <InsightsCard items={data.insights} /> : <Skeleton className="h-24" />}
      </Card>
    </div>
  );
}

// ── KPI ──────────────────────────────────────────────────────────────────────

const LEVEL_TEXT = { red: 'Đỏ', amber: 'Vàng', green: 'Xanh', grey: 'Xám' } as const;

type KpiProps = React.ComponentProps<typeof KpiTile>;

function buildKpis(
  data: DashboardV2 | undefined,
  fc: ReturnType<typeof useDashboardForecast>['data'],
  fcLoading: boolean,
  filters: DashboardFilterState,
): KpiProps[] {
  const n = (v: number | null | undefined) => (v == null ? '—' : v.toLocaleString('vi-VN'));

  // 1 · Số ca kỳ đã chốt (theo khối nếu đang lọc)
  const blockRow = filters.block === 'all' ? null : data?.cases.by_block.find((b) => b.block_code === filters.block);
  const cases = blockRow ? blockRow.cases_last_closed : data?.cases.last_closed.cases;
  const trend = blockRow ? blockRow.trend_pct : data?.cases.last_closed.trend_pct;
  const openCases = filters.block === 'all' ? data?.cases.open.cases : data?.trend.by_block[filters.block]?.slice(-1)[0]?.cases;

  // 2 · Dự báo kỳ tới
  const fcBlock = filters.block === 'all' ? null : fc?.blocks.find((b) => b.block === filters.block);
  const fcPoint = fc?.ready ? (fcBlock ? fcBlock.point : fc.total.point) : null;
  const fcLo = fcBlock ? fcBlock.lower : fc?.total.lower;
  const fcHi = fcBlock ? fcBlock.upper : fc?.total.upper;
  const members = fc?.blocks[0]?.model.members_used.length ?? null;
  const fcErr = fc && !fc.ready && fc.errors.length > 0;

  // 3 · Nguy cơ thiếu hụt
  const c = data?.risk.counts;

  // 4 · Mức nguy cơ chung
  const risk = data?.risk.overall;
  const riskTone: KpiTone = risk?.level === 'Cao' ? 'red' : risk?.level === 'Trung bình' ? 'amber' : risk ? 'green' : 'neutral';

  // 5 · Chất lượng dự báo
  const q = data?.quality;
  const cov = q?.by_block?.map((b) => (b.coverage_pct == null ? '—' : Math.round(b.coverage_pct))).join('/');

  return [
    {
      label: blockRow ? `Số ca ${filters.block} · kỳ chốt` : 'Số ca kỳ đã chốt',
      value: n(cases),
      unit: 'ca',
      tone: 'blue',
      to: ROUTES.EPIDEMIOLOGY,
      loading: !data,
      context: data ? (
        <span className="inline-flex items-center gap-1">
          Kỳ <b className="text-neutral-800">{data.meta.last_closed_period}</b>
          {trend != null && (
            <span className={cn('inline-flex items-center gap-0.5 font-semibold', trend >= 0 ? 'text-red-700' : 'text-emerald-700')}>
              {trend >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {Math.abs(trend).toFixed(1)}%
            </span>
          )}
          <span className="text-neutral-400">so với {data.meta.prev_closed_period}</span>
        </span>
      ) : undefined,
      footer: data?.meta.open_period ? (
        <>
          Kỳ {data.meta.open_period} đang mở: <b className="text-neutral-700">{n(openCases)}</b> ca · chưa chốt, không tính xu hướng
        </>
      ) : undefined,
    },
    {
      label: `Dự báo kỳ ${fc?.target_period ?? data?.meta.forecast_period ?? 'tới'}`,
      value: fcLoading ? <span className="text-base font-semibold text-neutral-400">đang tính…</span> : fcErr ? <span className="text-base font-semibold text-red-700">lỗi</span> : n(fcPoint != null ? Math.round(fcPoint) : null),
      unit: fcLoading || fcErr ? undefined : 'ca',
      tone: 'blue',
      to: ROUTES.SUPPLY_PLAN,
      context: fcLoading ? (
        <span className="text-neutral-500">Lần đầu khớp ensemble có thể mất tới một phút; các lần sau tức thì.</span>
      ) : fcErr ? (
        <span className="text-red-700">{fc?.errors[0]}</span>
      ) : fcLo != null && fcHi != null ? (
        <>
          Khoảng <b className="text-neutral-800 tabular-nums">{n(fcLo)}–{n(fcHi)}</b> · mức {Math.round((fc?.level ?? 0.9) * 100)}%
        </>
      ) : (
        <span className="text-neutral-500">Chưa đủ bước walk-forward để dựng khoảng</span>
      ),
      footer:
        fc?.ready && members != null ? (
          <>
            Ensemble {members} thành viên · top-down động{fc.blocks.some((b) => b.weather_used) ? ' · có thời tiết' : ''}
            {fc.ghi_chu.some((g) => g.includes('cận')) && <span className="text-amber-700"> · xem diễn giải</span>}
          </>
        ) : undefined,
    },
    {
      label: 'Nguy cơ thiếu hụt',
      value: n(c?.red),
      unit: 'mã Đỏ',
      tone: c && c.red > 0 ? 'red' : 'green',
      to: ROUTES.ALERTS,
      loading: !data,
      context: c ? (
        <span className="inline-flex flex-wrap gap-1">
          <LevelPill level="amber" label={`Vàng ${c.amber}`} />
          <LevelPill level="green" label={`Xanh ${c.green}`} />
          <LevelPill level="grey" label={`Xám ${c.grey}`} />
        </span>
      ) : undefined,
      footer: c ? (
        <>
          trên {n(c.total)} mã {data?.risk.selected} · DOI ≤ {c.nguong.red_days} ngày · {c.zero_stock} mã hết hàng
        </>
      ) : undefined,
    },
    {
      label: 'Mức nguy cơ chung',
      value: risk?.level ?? '—',
      tone: riskTone,
      to: ROUTES.ALERTS,
      loading: !data,
      context: risk ? <span className="text-neutral-500">{risk.basis}</span> : undefined,
      footer: risk?.is_provisional ? 'Tạm tính theo quy tắc, chưa phải suy luận thống kê' : undefined,
    },
    {
      label: 'Chất lượng dự báo',
      value: q?.available ? (q.rel_mae_codes ?? '—').toLocaleString('vi-VN') : <span className="text-base font-semibold text-neutral-400">chưa có</span>,
      unit: q?.available ? 'RelMAE' : undefined,
      tone: 'neutral',
      to: ROUTES.FORECASTING,
      loading: !data,
      context: q?.available ? (
        <>
          Tốt hơn seasonal naive <b className="text-emerald-700">{q.improvement_vs_naive_pct?.toFixed(1)}%</b> · độ phủ{' '}
          <b className="text-neutral-800 tabular-nums">{cov}%</b>
          <span className="text-neutral-400"> (mục tiêu {q.coverage_target_pct})</span>
        </>
      ) : (
        <span className="text-neutral-500">Chạy `run_eval.py --out ketqua_backtest` để có số chính thức</span>
      ),
      footer: q?.available ? (
        <>
          Backtest walk-forward {q.run_at ? new Date(q.run_at).toLocaleDateString('vi-VN') : ''} · {q.phuong_an}
          {q.canh_bao && <span className="text-amber-700"> · {q.canh_bao}</span>}
        </>
      ) : undefined,
    },
  ];
}

// ── Khung thẻ ────────────────────────────────────────────────────────────────

function Card({
  title,
  subtitle,
  right,
  children,
  className,
  bodyClassName,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={cn('bg-white rounded-2xl border border-neutral-200', className)}>
      <header className="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
        <div className="min-w-0">
          <h3 className="font-semibold text-neutral-900 text-[15px] leading-tight">{title}</h3>
          {subtitle && <p className="text-xs text-neutral-500 mt-0.5">{subtitle}</p>}
        </div>
        {right}
      </header>
      <div className={cn('px-5 pb-5', bodyClassName)}>{children}</div>
    </section>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={cn('rounded-xl bg-neutral-100 animate-pulse', className)} />;
}
