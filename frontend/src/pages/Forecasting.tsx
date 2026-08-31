import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, Loader2, AlertCircle, History, LineChart } from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import {
  useAnalyzeForecast,
  useDiseaseOptions,
  useForecastHistory,
} from '../hooks/useForecastAnalysis';
import api from '../services/api';
import type { AnalyzeResponse } from '../services/forecastAnalysisService';
import { forecastAnalysisService } from '../services/forecastAnalysisService';
import ForecastFilterBar, {
  type ForecastFilters,
} from '../components/forecasting/ForecastFilterBar';
import ForecastResultCard from '../components/forecasting/ForecastResultCard';
import ModelExplanation from '../components/forecasting/ModelExplanation';
import ForecastVsActualChart from '../components/forecasting/ForecastVsActualChart';
import ComparisonChart from '../components/forecasting/ComparisonChart';
import CurrentYearTrendChart from '../components/forecasting/CurrentYearTrendChart';
import CorrelationChart from '../components/forecasting/CorrelationChart';
import RecentMonthDataTable from '../components/forecasting/RecentMonthDataTable';
import ForecastHistoryTable from '../components/forecasting/ForecastHistoryTable';
import { cn } from '../utils/cn';

/**
 * Module 5 — Phân tích & Dự báo số ca bệnh
 * Theo design của Smart Medical System.
 */
export default function Forecasting() {
  const { setPageTitle } = useUIStore();

  useEffect(() => {
    setPageTitle('Phân tích & Dự báo');
  }, [setPageTitle]);

  const [tab, setTab] = useState<'phan-tich' | 'lich-su'>('phan-tich');

  // Default tháng dự báo = tháng hiện tại
  const defaultMonth = useMemo(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  }, []);

  // Lưu filters vào localStorage để persist khi navigate. Kết quả phân tích
  // KHÔNG persist qua localStorage nữa (từng gây lệch — hiển thị kết quả cũ
  // không khớp bộ lọc đang chọn). Thay vào đó: effect auto-load bên dưới tự
  // gọi /forecast/analyze với force_refresh=false mỗi khi chọn đúng bộ lọc
  // (bệnh, khu vực, tháng) — backend trả lại kết quả đã lưu cho đúng 3 tiêu
  // chí này nếu có, hoặc tính mới nếu chưa từng phân tích.
  const [filters, setFilters] = useState<ForecastFilters>(() => {
    try {
      const saved = localStorage.getItem('forecast_filters');
      if (saved) {
        return JSON.parse(saved);
      }
    } catch {
      // ignore
    }
    return {
      disease: 'dengue_fever',
      province: 'all',
      month: defaultMonth,
    };
  });

  // Sync filters to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('forecast_filters', JSON.stringify(filters));
  }, [filters]);

  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [exporting, setExporting] = useState(false);

  const { data: diseases = [] } = useDiseaseOptions();

  // Map cascade tỉnh → list quận có data thực trong DB (gộp từ disease + environmental)
  const [regionDistricts, setRegionDistricts] = useState<Record<string, string[]>>({});
  useEffect(() => {
    const load = async () => {
      try {
        const [d1, d2] = await Promise.all([
          api
            .get('/disease-cases/distinct-values')
            .then((r) => r.data?.region_districts ?? {})
            .catch(() => ({})),
          api
            .get('/environmental/distinct-values')
            .then((r) => r.data?.province_districts ?? {})
            .catch(() => ({})),
        ]);
        const merged: Record<string, string[]> = {};
        const addAll = (m: Record<string, string[]>) => {
          for (const [prov, dists] of Object.entries(m)) {
            for (const d of dists as string[]) {
              if (!prov || !d) continue;
              merged[prov] = merged[prov] || [];
              if (!merged[prov].includes(d)) merged[prov].push(d);
            }
          }
        };
        addAll(d1 as Record<string, string[]>);
        addAll(d2 as Record<string, string[]>);
        setRegionDistricts(merged);
      } catch {
        /* ignore */
      }
    };
    load();
  }, []);

  const analyze = useAnalyzeForecast();

  const runAnalyze = (forceRefresh: boolean) => {
    if (!filters.disease || !filters.month) {
      console.warn('[Forecasting] missing disease or month', filters);
      return;
    }
    const [yStr, mStr] = filters.month.split('-');
    // Sử dụng tỉnh hoặc null (toàn quốc)
    const regionValue = filters.province !== 'all' ? filters.province : null;
    const payload = {
      disease_type: filters.disease,
      region: regionValue,
      target_month: Number(mStr),
      target_year: Number(yStr),
      force_refresh: forceRefresh,
    };
    console.log('[Forecasting] analyze payload', payload);
    analyze.mutate(payload, {
      onSuccess: (data) => {
        console.log('[Forecasting] analyze ok', data.forecast);
        setResult(data);
      },
      onError: (err) => {
        console.error('[Forecasting] analyze failed', err);
      },
    });
  };

  // Auto-pick disease nếu list có dữ liệu mà filters đang trống
  useEffect(() => {
    if (diseases.length > 0 && !diseases.some((d) => d.key === filters.disease)) {
      setFilters((f) => ({ ...f, disease: diseases[0].key }));
    }
  }, [diseases, filters.disease]);

  // ── Auto-load: mỗi khi bộ lọc (bệnh, khu vực, tháng) hợp lệ thay đổi, tự
  // gọi /forecast/analyze với force_refresh=false — người dùng không cần bấm
  // nút khi chỉ xem lại phân tích đã làm trước đó cho đúng bộ lọc này; nút
  // "Phân tích lại" (force_refresh=true) dùng khi muốn ép tính lại từ đầu.
  const lastAutoKey = useRef<string | null>(null);
  useEffect(() => {
    if (!filters.disease || !filters.month) return;
    const key = `${filters.disease}|${filters.province}|${filters.month}`;
    if (lastAutoKey.current === key) return;
    lastAutoKey.current = key;
    runAnalyze(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.disease, filters.province, filters.month]);

  // Kết quả hiển thị lấy thẳng từ /analyze (backend đã dùng mô hình AI tính
  // số ca + mức nguy cơ và lưu DB), nên card, biểu đồ, bảng đều nhất quán.
  const displayResult = result;

  const targetMonthNum = displayResult?.forecast.target_month ?? Number(filters.month.split('-')[1]);
  const targetYearNum = displayResult?.forecast.target_year ?? Number(filters.month.split('-')[0]);

  const analyzedAtLabel = useMemo(() => {
    const iso = displayResult?.forecast.analyzed_at;
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleString('vi-VN', {
        dateStyle: 'short',
        timeStyle: 'short',
      });
    } catch {
      return null;
    }
  }, [displayResult?.forecast.analyzed_at]);

  const history = useForecastHistory({ limit: 200 }, { enabled: tab === 'lich-su' });

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">
            Dự báo số ca bệnh
          </h2>
          <p className="text-sm text-neutral-500 mt-1">
            Phân tích đa biến dựa trên dữ liệu lịch sử và yếu tố thời tiết.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={!result || exporting}
            onClick={async () => {
              if (!result?.forecast?.id) return;
              try {
                setExporting(true);
                const blob = await forecastAnalysisService.exportForecastPdf(
                  result.forecast.id,
                );
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `forecast_${result.forecast.id}.pdf`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
              } catch (err) {
                console.error(err);
                alert('Không thể xuất báo cáo. Vui lòng thử lại.');
              } finally {
                setExporting(false);
              }
            }}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed"
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

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-neutral-200">
        <TabButton
          active={tab === 'phan-tich'}
          onClick={() => setTab('phan-tich')}
          icon={<LineChart className="w-4 h-4" />}
          label="Phân tích"
        />
        <TabButton
          active={tab === 'lich-su'}
          onClick={() => setTab('lich-su')}
          icon={<History className="w-4 h-4" />}
          label="Lịch sử phân tích"
        />
      </div>

      {tab === 'lich-su' ? (
        <ForecastHistoryTable
          rows={history.data ?? []}
          isLoading={history.isLoading}
          onUpdated={() => history.refetch()}
        />
      ) : (
        <>
          {/* Filter bar */}
          <ForecastFilterBar
            filters={filters}
            onChange={setFilters}
            onAnalyze={() => runAnalyze(true)}
            diseases={diseases}
            regionDistricts={regionDistricts}
            isLoading={analyze.isPending}
            buttonLabel={result ? 'Phân tích lại' : 'Phân tích'}
          />

          {/* Badge: đã phân tích lúc ... / dùng lại kết quả đã lưu */}
          {displayResult && !analyze.isPending && (
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <span
                className={cn(
                  'inline-flex items-center gap-1 px-2 py-1 rounded-full font-medium',
                  displayResult.forecast.from_cache
                    ? 'bg-neutral-100 text-neutral-600'
                    : 'bg-emerald-50 text-emerald-700',
                )}
              >
                {displayResult.forecast.from_cache ? 'Kết quả đã lưu' : 'Vừa phân tích'}
              </span>
              {analyzedAtLabel && <span>Đã phân tích lúc {analyzedAtLabel}</span>}
            </div>
          )}

          {/* Error */}
          {analyze.isError && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                Không thể chạy phân tích:{' '}
                {(analyze.error as Error)?.message || 'Đã xảy ra lỗi.'}
              </span>
            </div>
          )}

          {/* Empty state khi chưa phân tích */}
          {!result && !analyze.isPending && !analyze.isError && (
            <div className="rounded-2xl border border-dashed border-neutral-200 bg-white p-10 text-center">
              <p className="text-sm text-neutral-500">
                Chọn bệnh, khu vực và tháng cần dự báo — kết quả sẽ tự hiển thị.
              </p>
            </div>
          )}

          {/* Loading skeleton */}
          {analyze.isPending && (
            <div className="rounded-2xl border border-neutral-200 bg-white p-10 flex items-center justify-center text-neutral-500 text-sm gap-2">
              <Loader2 className="w-5 h-5 animate-spin" />
              Đang phân tích dữ liệu...
            </div>
          )}

          {/* Result */}
          {displayResult && !analyze.isPending && (
            <>
              {/* Row 1: Forecast card + Main chart */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="space-y-5 lg:col-span-1">
                  <ForecastResultCard
                    predictedCases={displayResult.forecast.predicted_cases}
                    diseaseLabel={displayResult.forecast.disease_label}
                    region={displayResult.forecast.region}
                    targetMonth={displayResult.forecast.target_month}
                    targetYear={displayResult.forecast.target_year}
                    riskLevel={displayResult.forecast.risk_level}
                    riskLabel={displayResult.forecast.risk_label}
                    accuracyPct={
                      displayResult.accuracy != null
                        ? Math.max(0, 100 - displayResult.accuracy.mape)
                        : null
                    }
                  />
                  <ModelExplanation bullets={displayResult.explanation_bullets} />
                </div>

                <div className="lg:col-span-2">
                  <ForecastVsActualChart
                    data={displayResult.charts.main as Array<Record<string, number | string>>}
                    years={displayResult.charts.years}
                    targetYear={targetYearNum}
                    targetMonth={targetMonthNum}
                  />
                </div>
              </div>

              {/* Row 2: Comparison + Current year trend */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <ComparisonChart
                  data={displayResult.charts.comparison}
                  targetMonth={targetMonthNum}
                />
                <CurrentYearTrendChart
                  data={displayResult.charts.trend_current_year}
                  targetYear={targetYearNum}
                  upToMonth={targetMonthNum > 1 ? targetMonthNum - 1 : 1}
                />
              </div>

              {/* Row 3: Correlation chart full width */}
              <CorrelationChart
                data={displayResult.charts.correlation}
                targetMonth={targetMonthNum}
                coefficients={displayResult.charts.correlation_coefficients}
              />

              {/* Row 4: Dữ liệu ca bệnh gần đây */}
              <RecentMonthDataTable
                key={displayResult.forecast.id} // Force reload khi có forecast mới
                currentMonth={targetMonthNum}
                currentYear={targetYearNum}
                diseaseLabel={displayResult.forecast.disease_label}
                regionFilter={filters.province}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition',
        active
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-neutral-500 hover:text-neutral-700',
      )}
    >
      {icon}
      {label}
    </button>
  );
}
