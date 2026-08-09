import { useEffect, useState } from 'react';
import {
  Activity,
  BarChart3,
  Inbox,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  Download,
  Loader2,
  RefreshCw,
  Check,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  Cell,
} from 'recharts';
import { useUIStore } from '../store/uiStore';
import {
  useDashboardSummary,
  useCaseTrend,
  useDemandVsStock,
  useDashboardCriticalAlerts,
} from '../hooks/useDashboard';
import LoadingSpinner from '../components/common/LoadingSpinner';
import EpidemicMapCard from '../components/dashboard/EpidemicMapCard';
import { Link, useNavigate } from 'react-router-dom';
import { ROUTES } from '../utils/constants';
import { reportsService } from '../services/reportsService';
import { SERIES, INK, gridProps, tooltipStyle } from '../utils/chartTheme';

export default function Dashboard() {
  const { setPageTitle } = useUIStore();
  const navigate = useNavigate();
  const [exporting, setExporting] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);

  const { data: summary, isLoading: loadingSummary, dataUpdatedAt, refetch: refetchSummary } = useDashboardSummary();
  const { data: trend, isLoading: loadingTrend, refetch: refetchTrend } = useCaseTrend(6);
  const { data: demand, isLoading: loadingDemand, refetch: refetchDemand } = useDemandVsStock(5);
  const { data: alerts, isLoading: loadingAlerts, refetch: refetchAlerts } = useDashboardCriticalAlerts(5);

  const handleRefresh = async () => {
    if (refreshing) return;
    try {
      setRefreshing(true);
      await Promise.all([
        refetchSummary(),
        refetchTrend(),
        refetchDemand(),
        refetchAlerts(),
      ]);
      setRefreshedAt(Date.now());
    } catch (err) {
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  };

  // Tự ẩn thông báo "đã cập nhật" sau vài giây
  useEffect(() => {
    if (refreshedAt === null) return;
    const timer = setTimeout(() => setRefreshedAt(null), 2500);
    return () => clearTimeout(timer);
  }, [refreshedAt]);

  useEffect(() => {
    setPageTitle('Dashboard Tổng quan');
  }, [setPageTitle]);

  const handleExport = async () => {
    if (exporting) return;
    try {
      setExporting(true);
      const blob = await reportsService.exportReport({ report_type: 'dashboard-summary' as any });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `dashboard_summary_${new Date()
        .toISOString()
        .replace(/[-:T]/g, '')
        .slice(0, 14)}.pdf`;
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

  const lastUpdated = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    : '—';

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">Tổng quan Hệ thống</h2>
          <p className="text-sm text-neutral-500 mt-1">
            Dữ liệu cập nhật lúc {lastUpdated}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {refreshedAt !== null && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-50 border border-green-100 rounded-lg text-sm font-medium text-green-700 transition-opacity">
              <Check className="w-4 h-4" />
              Đã cập nhật
            </span>
          )}
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-60 disabled:cursor-not-allowed"
            title="Làm mới dữ liệu"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? 'Đang tải...' : 'Làm mới'}
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-100 rounded-xl text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {exporting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            {exporting ? 'Đang xuất...' : 'Xuất báo cáo'}
          </button>
        </div>
      </div>

      {/* KPI Row */}
      {loadingSummary ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="bg-white rounded-2xl border border-neutral-200 h-32 flex items-center justify-center"
            >
              <LoadingSpinner size="md" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
          <KpiCard
            title={
              (summary as any)?.as_of
                ? `TỔNG SỐ CA (T${new Date((summary as any).as_of).getMonth() + 1}/${new Date((summary as any).as_of).getFullYear()})`
                : 'TỔNG SỐ CA HIỆN TẠI'
            }
            value={summary?.total_cases_current?.toLocaleString('vi-VN') ?? '—'}
            icon={<Activity className="w-5 h-5" />}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
            to={ROUTES.EPIDEMIOLOGY}
            badge={
              summary && summary.cases_trend_pct !== undefined
                ? { type: 'trend', value: summary.cases_trend_pct }
                : null
            }
          />
          <KpiCard
            title="DỰ BÁO THÁNG TỚI"
            value={summary?.predicted_cases_next_month?.toLocaleString('vi-VN') ?? '—'}
            icon={<BarChart3 className="w-5 h-5" />}
            iconBg="bg-amber-50"
            iconColor="text-amber-700"
            to={ROUTES.FORECASTING}
            badge={
              summary && summary.predicted_trend_pct !== undefined
                ? { type: 'trend', value: summary.predicted_trend_pct }
                : null
            }
          />
          <KpiCard
            title="VẬT TƯ THIẾU HỤT"
            value={
              <span className="text-red-600">
                {summary?.shortage_supplies_count ?? 0}
                <span className="ml-1 text-base font-medium text-neutral-400">mục</span>
              </span>
            }
            icon={<Inbox className="w-5 h-5" />}
            iconBg="bg-red-50"
            iconColor="text-red-600"
            to={ROUTES.ALERTS}
            badge={
              (summary?.shortage_supplies_count ?? 0) > 0
                ? { type: 'pill', text: '⚠ Cần nhập', tone: 'red' }
                : { type: 'pill', text: '✓ Đầy đủ', tone: 'green' }
            }
          />
          <KpiCard
            title="MỨC NGUY CƠ CHUNG"
            value={
              <span className={`${riskColor(summary?.overall_risk)}`}>
                {summary?.overall_risk ?? '—'}
              </span>
            }
            icon={<ShieldAlert className="w-5 h-5" />}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
            to={ROUTES.ALERTS}
          />
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <ChartCard
          title="Xu hướng ca bệnh"
          right={<ChartLegendChips items={[{ label: 'Năm nay', color: SERIES.s1 }, { label: 'Năm trước', color: INK.reference }]} />}
        >
          {loadingTrend ? (
            <div className="h-72 flex items-center justify-center">
              <LoadingSpinner size="md" />
            </div>
          ) : (
            <CaseTrendChart trend={trend} />
          )}
        </ChartCard>

        <ChartCard
          title="Nhu cầu vs Tồn kho"
          subtitle="Vật tư chính"
          right={<ChartLegendChips items={[{ label: 'Tồn kho', color: SERIES.s1 }, { label: 'Dự kiến nhu cầu', color: SERIES.s4 }]} />}
        >
          {loadingDemand ? (
            <div className="h-72 flex items-center justify-center">
              <LoadingSpinner size="md" />
            </div>
          ) : (
            <DemandVsStockChart data={demand ?? []} />
          )}
        </ChartCard>
      </div>

      {/* Critical alerts table + Map */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden lg:col-span-2">
          <div className="flex items-center justify-between px-6 py-4">
            <h3 className="font-semibold text-neutral-900 text-base">
              Cảnh báo thiếu hụt vật tư
            </h3>
            <Link
              to={ROUTES.ALERTS}
              className="text-sm text-blue-600 hover:underline font-medium"
            >
              Xem tất cả
            </Link>
          </div>

          {loadingAlerts ? (
            <div className="h-32 flex items-center justify-center">
              <LoadingSpinner size="sm" />
            </div>
          ) : (alerts?.length ?? 0) === 0 ? (
            <div className="py-10 text-center text-sm text-neutral-400">
              Không có cảnh báo
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-neutral-500 text-xs">
                  <th className="text-left px-6 py-3 font-medium">Tên Vật Tư</th>
                  <th className="text-left px-6 py-3 font-medium">Kho hiện tại</th>
                  <th className="text-left px-6 py-3 font-medium">Định mức an toàn</th>
                  <th className="text-left px-6 py-3 font-medium">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {alerts!.map((a) => (
                  <tr
                    key={a.id}
                    onClick={() => navigate(ROUTES.ALERTS)}
                    className="border-t border-neutral-100 hover:bg-neutral-50 cursor-pointer"
                  >
                    <td className="px-6 py-3 text-neutral-700">{a.supply_name}</td>
                    <td className="px-6 py-3">
                      {a.current_stock?.toLocaleString('vi-VN') ?? 0}
                    </td>
                    <td className="px-6 py-3">
                      {a.required_stock?.toLocaleString('vi-VN') ?? 0}
                    </td>
                    <td className="px-6 py-3">
                      <SeverityBadge severity={a.severity} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <EpidemicMapCard />
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

interface KpiBadge {
  type: 'trend' | 'pill';
  value?: number;
  text?: string;
  tone?: 'red' | 'green';
}

function KpiCard({
  title,
  value,
  icon,
  iconBg,
  iconColor,
  badge,
  to,
}: {
  title: string;
  value: React.ReactNode;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
  badge?: KpiBadge | null;
  to?: string;
}) {
  const navigate = useNavigate();
  const interactive = !!to;
  const handleClick = () => {
    if (to) navigate(to);
  };
  return (
    <div
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={interactive ? handleClick : undefined}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleClick();
              }
            }
          : undefined
      }
      className={
        'bg-white rounded-2xl border border-neutral-200 p-5 transition ' +
        (interactive
          ? 'cursor-pointer hover:shadow-card-hover hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-blue-500/40'
          : '')
      }
    >
      <div className="flex items-center justify-between">
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${iconBg} ${iconColor}`}>
          {icon}
        </div>
        {badge?.type === 'trend' && typeof badge.value === 'number' && (
          <span
            className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full ${
              badge.value >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
            }`}
          >
            {badge.value >= 0 ? (
              <ArrowUpRight className="w-3 h-3" />
            ) : (
              <ArrowDownRight className="w-3 h-3" />
            )}
            {Math.abs(badge.value).toFixed(0)}%
          </span>
        )}
        {badge?.type === 'pill' && (
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
              badge.tone === 'red'
                ? 'bg-red-50 text-red-700'
                : 'bg-emerald-50 text-emerald-700'
            }`}
          >
            {badge.text}
          </span>
        )}
      </div>
      <p className="text-[11px] uppercase tracking-wider text-neutral-500 font-semibold mt-4">
        {title}
      </p>
      <p className="text-3xl font-extrabold text-neutral-900 mt-1">{value}</p>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h3 className="font-semibold text-neutral-900 text-base">{title}</h3>
          {subtitle && <p className="text-sm text-neutral-500 mt-0.5">{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </div>
  );
}

function ChartLegendChips({ items }: { items: Array<{ label: string; color: string }> }) {
  return (
    <div className="flex items-center gap-2">
      {items.map((it) => (
        <div
          key={it.label}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-neutral-50 border border-neutral-100 text-xs text-neutral-600"
        >
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: it.color }}
          />
          {it.label}
        </div>
      ))}
    </div>
  );
}

function CaseTrendChart({ trend }: { trend: any }) {
  if (!trend || trend.this_year.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center text-sm text-neutral-400">
        Chưa có dữ liệu xu hướng
      </div>
    );
  }
  const merged = trend.this_year.map((p: any, idx: number) => ({
    month: p.month,
    'Năm nay': p.value,
    'Năm trước': trend.last_year[idx]?.value ?? 0,
  }));

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={merged} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fill: INK.axis, fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: INK.axis, fontSize: 11 }} width={40} />
          <Tooltip {...tooltipStyle} />
          <Legend wrapperStyle={{ display: 'none' }} />
          <Line
            type="monotone"
            dataKey="Năm trước"
            stroke={INK.reference}
            strokeWidth={2}
            strokeDasharray="4 4"
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="Năm nay"
            stroke={SERIES.s1}
            strokeWidth={2.5}
            dot={{ r: 3, strokeWidth: 2, stroke: '#ffffff', fill: SERIES.s1 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function DemandVsStockChart({ data }: { data: any[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="h-72 flex items-center justify-center text-sm text-neutral-400">
        Chưa có dữ liệu nhu cầu
      </div>
    );
  }
  const formatted = data.map((d) => ({
    name: d.supply_name.length > 18 ? d.supply_name.slice(0, 16) + '…' : d.supply_name,
    full: d.supply_name,
    'Tồn kho': d.stock,
    'Dự kiến nhu cầu': d.demand,
  }));
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={formatted} margin={{ top: 8, right: 12, left: 0, bottom: 24 }}>
          <CartesianGrid {...gridProps} />
          <XAxis
            dataKey="name"
            tickLine={false}
            axisLine={false}
            tick={{ fill: INK.axis, fontSize: 11 }}
            interval={0}
          />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: INK.axis, fontSize: 11 }} width={44} />
          <Tooltip
            {...tooltipStyle}
            cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
            labelFormatter={(label, payload) => payload?.[0]?.payload?.full || label}
          />
          <Legend wrapperStyle={{ display: 'none' }} />
          <Bar dataKey="Tồn kho" fill={SERIES.s1} radius={[4, 4, 0, 0]} barSize={20}>
            {formatted.map((_, i) => (
              <Cell key={`a-${i}`} />
            ))}
          </Bar>
          <Bar dataKey="Dự kiến nhu cầu" fill={SERIES.s4} radius={[4, 4, 0, 0]} barSize={20}>
            {formatted.map((_, i) => (
              <Cell key={`b-${i}`} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SeverityBadge({ severity }: { severity?: string | null }) {
  const map: Record<string, { label: string; className: string; dot: string }> = {
    critical: { label: 'Nguy hiểm', className: 'bg-red-50 text-red-700', dot: 'bg-red-500' },
    high: { label: 'Cần nhập', className: 'bg-orange-50 text-orange-700', dot: 'bg-orange-500' },
    medium: { label: 'Cảnh báo', className: 'bg-amber-50 text-amber-700', dot: 'bg-amber-500' },
  };
  const m =
    map[severity ?? ''] ??
    { label: severity ?? '—', className: 'bg-neutral-100 text-neutral-600', dot: 'bg-neutral-400' };
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${m.className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />
      {m.label}
    </span>
  );
}

function riskColor(level?: string): string {
  if (level === 'Cao') return 'text-red-600';
  if (level === 'Trung bình') return 'text-amber-700';
  if (level === 'Thấp') return 'text-emerald-600';
  return 'text-neutral-700';
}
