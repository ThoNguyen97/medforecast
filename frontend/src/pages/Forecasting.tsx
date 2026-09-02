import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  Download,
  Loader2,
  AlertCircle,
  History,
  LineChart,
  Save,
  CheckCircle2,
} from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import {
  useAnalyzeForecast,
  useDiseaseOptions,
  useForecastHistory,
  useSavedForecast,
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

/** Khoá sessionStorage giữ bản phân tích chưa ghi nhận (kèm khoá bộ lọc). */
const KHOA_PHAN_TICH_TAM = 'forecast_phan_tich_tam';

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
  // KHÔNG persist qua localStorage (từng gây lệch — hiển thị kết quả cũ không
  // khớp bộ lọc đang chọn). Thay vào đó: effect bên dưới gọi /forecast/saved
  // để nạp lại bản ĐÃ GHI NHẬN theo đúng khóa (nhóm bệnh, tỉnh/thành, tháng);
  // chưa ghi nhận thì để trống, chờ người dùng bấm "Phân tích".
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

  // Kết quả VỪA PHÂN TÍCH (chưa ghi nhận). Được ưu tiên hiển thị. Ngoài state,
  // nó còn được gửi tạm vào sessionStorage kèm khoá bộ lọc: rời sang menu khác
  // rồi quay lại là component bị huỷ, không lưu thì mất trắng công phân tích.
  const [phanTichMoi, setPhanTichMoi] = useState<AnalyzeResponse | null>(null);
  /** Thời điểm chạy phân tích tạm (ms) — để hiện "Phân tích lúc ...". */
  const [phanTichLuc, setPhanTichLuc] = useState<number | null>(null);
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
  const queryClient = useQueryClient();

  // Hộp hỏi ghi đè khi kỳ này đã có dự báo được ghi nhận trước đó.
  const [xacNhanGhiDe, setXacNhanGhiDe] = useState<string | null>(null);

  /** Khoá nhận dạng bộ lọc hiện tại — dùng cho bộ nhớ tạm. */
  const khoaLoc = `${filters.disease}|${filters.province}|${filters.month}`;

  const luuTam = (data: AnalyzeResponse, luc: number) => {
    try {
      sessionStorage.setItem(
        KHOA_PHAN_TICH_TAM,
        JSON.stringify({ khoa: khoaLoc, luc, ketQua: data }),
      );
    } catch {
      // Hết chỗ lưu thì thôi — chỉ mất tiện ích, không ảnh hưởng kết quả.
    }
  };

  const xoaTam = () => {
    try {
      sessionStorage.removeItem(KHOA_PHAN_TICH_TAM);
    } catch {
      /* bỏ qua */
    }
  };

  /** Payload theo đúng bộ lọc hiện tại; null nếu bộ lọc chưa đủ. */
  const buildPayload = () => {
    if (!filters.disease || !filters.month) return null;
    const [yStr, mStr] = filters.month.split('-');
    return {
      disease_type: filters.disease,
      region: filters.province !== 'all' ? filters.province : null,
      target_month: Number(mStr),
      target_year: Number(yStr),
    };
  };

  /** Bấm "Phân tích": chạy mô hình để XEM, không ghi gì vào DB. */
  const runAnalyze = () => {
    const payload = buildPayload();
    if (!payload) return;
    analyze.mutate(
      { ...payload, save: false },
      {
        onSuccess: (data) => {
          const luc = Date.now();
          setPhanTichMoi(data);
          setPhanTichLuc(luc);
          luuTam(data, luc);
        },
        onError: (err) => console.error('[Forecasting] analyze failed', err),
      },
    );
  };

  /** Bấm "Ghi nhận dự báo": lưu kết quả. Kỳ đã có bản ghi nhận → hỏi ghi đè. */
  const ghiNhan = (overwrite: boolean) => {
    const payload = buildPayload();
    if (!payload) return;
    setXacNhanGhiDe(null);
    analyze.mutate(
      { ...payload, save: true, overwrite },
      {
        onSuccess: (data) => {
          // Backend báo kỳ này đã có bản ghi nhận → hỏi ghi đè, giữ nguyên
          // kết quả đang hiển thị trên màn hình.
          if (data?.conflict) {
            setXacNhanGhiDe(
              data.message ??
                'Kỳ này đã có dự báo được ghi nhận trước đó. Ghi đè bản cũ?',
            );
            return;
          }
          setPhanTichMoi(data);
          setPhanTichLuc(null);
          xoaTam(); // đã nằm trong DB, không cần bản tạm nữa
          // Bản ghi nhận vừa tạo → làm mới cache đọc + lịch sử
          queryClient.invalidateQueries({ queryKey: ['forecast', 'saved'] });
          queryClient.invalidateQueries({ queryKey: ['forecast', 'history'] });
        },
        onError: (err: any) => {
          console.error('[Forecasting] ghi nhan failed', err);
          alert('Không ghi nhận được: ' + (err?.message ?? ''));
        },
      },
    );
  };

  // Auto-pick disease nếu list có dữ liệu mà filters đang trống
  useEffect(() => {
    if (diseases.length > 0 && !diseases.some((d) => d.key === filters.disease)) {
      setFilters((f) => ({ ...f, disease: diseases[0].key }));
    }
  }, [diseases, filters.disease]);

  // ── Mở trang / đổi bộ lọc: CHỈ nạp bản đã ghi nhận theo khóa
  // (Nhóm bệnh, Tỉnh/Thành, Tháng dự báo). Không bao giờ tự chạy mô hình —
  // muốn phân tích thì phải bấm nút "Phân tích".
  const savedKey = useMemo(
    () => (filters.disease && filters.month ? buildPayload() : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [filters.disease, filters.province, filters.month],
  );
  const savedQuery = useSavedForecast(savedKey);

  // Mở trang / đổi bộ lọc: khôi phục bản phân tích tạm NẾU đúng bộ lọc này,
  // ngược lại bỏ đi (tránh hiện kết quả của bộ lọc khác).
  useEffect(() => {
    setXacNhanGhiDe(null);
    analyze.reset();
    try {
      const raw = sessionStorage.getItem(KHOA_PHAN_TICH_TAM);
      const luu = raw ? JSON.parse(raw) : null;
      if (luu && luu.khoa === khoaLoc && luu.ketQua) {
        setPhanTichMoi(luu.ketQua as AnalyzeResponse);
        setPhanTichLuc(typeof luu.luc === 'number' ? luu.luc : null);
        return;
      }
    } catch {
      /* dữ liệu tạm hỏng → coi như chưa có */
    }
    setPhanTichMoi(null);
    setPhanTichLuc(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [khoaLoc]);

  // Ưu tiên bản vừa phân tích (chưa ghi nhận), nếu không có thì lấy bản đã ghi nhận.
  const displayResult = phanTichMoi ?? savedQuery.data ?? null;
  // isLoading (không phải isFetching): chỉ hiện spinner khi thật sự chưa có dữ
  // liệu cho khóa đang chọn, tránh chớp màn hình khi làm mới ngầm sau khi ghi nhận.
  const dangNap = savedQuery.isLoading || analyze.isPending;

  const targetMonthNum = displayResult?.forecast.target_month ?? Number(filters.month.split('-')[1]);
  const targetYearNum = displayResult?.forecast.target_year ?? Number(filters.month.split('-')[0]);

  const daGhiNhan = !!displayResult?.forecast.is_recorded;

  const analyzedAtLabel = useMemo(() => {
    const iso = displayResult?.forecast.recorded_at;
    if (!iso) return null;
    try {
      return new Date(iso).toLocaleString('vi-VN', {
        dateStyle: 'short',
        timeStyle: 'short',
      });
    } catch {
      return null;
    }
  }, [displayResult?.forecast.recorded_at]);

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
            disabled={!displayResult?.forecast?.id || exporting}
            title={
              displayResult && !displayResult.forecast.id
                ? 'Cần ghi nhận dự báo trước khi xuất báo cáo'
                : undefined
            }
            onClick={async () => {
              if (!displayResult?.forecast?.id) return;
              try {
                setExporting(true);
                const blob = await forecastAnalysisService.exportForecastPdf(
                  displayResult.forecast.id,
                );
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `forecast_${displayResult.forecast.id}.pdf`;
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
          onChanged={() => {
            history.refetch();
            // Bản vừa xoá có thể chính là bản đang hiển thị ở tab Phân tích
            queryClient.invalidateQueries({ queryKey: ['forecast', 'saved'] });
          }}
        />
      ) : (
        <>
          {/* Filter bar */}
          <ForecastFilterBar
            filters={filters}
            onChange={setFilters}
            onAnalyze={runAnalyze}
            diseases={diseases}
            regionDistricts={regionDistricts}
            isLoading={dangNap}
            buttonLabel={daGhiNhan ? 'Phân tích lại' : 'Phân tích'}
          />

          {/* Trạng thái ghi nhận + nút Ghi nhận dự báo */}
          {displayResult && !dangNap && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
              <span
                className={cn(
                  'inline-flex items-center gap-1 px-2 py-1 rounded-full font-medium',
                  daGhiNhan
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-amber-50 text-amber-700',
                )}
              >
                {daGhiNhan ? 'Đã ghi nhận' : 'Chưa ghi nhận'}
              </span>
              {daGhiNhan && analyzedAtLabel && (
                <span>Ghi nhận lúc {analyzedAtLabel}</span>
              )}
              {!daGhiNhan && phanTichLuc && (
                <span>
                  Phân tích lúc{' '}
                  {new Date(phanTichLuc).toLocaleString('vi-VN', {
                    dateStyle: 'short',
                    timeStyle: 'short',
                  })}
                </span>
              )}

              <button
                type="button"
                onClick={() => ghiNhan(false)}
                disabled={analyze.isPending}
                className={cn(
                  'ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition disabled:opacity-60',
                  daGhiNhan
                    ? 'text-neutral-700 bg-white border border-neutral-200 hover:bg-neutral-50'
                    : 'text-white bg-emerald-600 hover:bg-emerald-700 shadow-sm',
                )}
              >
                {daGhiNhan ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : (
                  <Save className="w-3.5 h-3.5" />
                )}
                {daGhiNhan ? 'Ghi nhận lại' : 'Ghi nhận dự báo'}
              </button>
            </div>
          )}

          {/* Lỗi khi nạp bản đã ghi nhận */}
          {savedQuery.isError && !savedQuery.isFetching && (
            <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                Không nạp được dự báo đã ghi nhận:{' '}
                {(savedQuery.error as Error)?.message || 'Không rõ nguyên nhân.'}
                <br />
                <span className="text-red-600/80">
                  Nếu vừa cập nhật mã nguồn, hãy khởi động lại backend để có
                  endpoint mới rồi tải lại trang.
                </span>
              </span>
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

          {/* Chưa ghi nhận dự báo nào cho khóa đang chọn */}
          {!displayResult && !dangNap && !analyze.isError && !savedQuery.isError && (
            <div className="rounded-2xl border border-dashed border-neutral-200 bg-white p-10 text-center">
              <p className="text-sm text-neutral-500">
                Chưa có dự báo được ghi nhận cho nhóm bệnh, tỉnh/thành và tháng
                đang chọn.
              </p>
              <p className="text-sm text-neutral-500 mt-1">
                Bấm <span className="font-semibold text-blue-600">Phân tích</span>{' '}
                để chạy dự báo.
              </p>
            </div>
          )}

          {/* Loading skeleton */}
          {dangNap && (
            <div className="rounded-2xl border border-neutral-200 bg-white p-10 flex items-center justify-center text-neutral-500 text-sm gap-2">
              <Loader2 className="w-5 h-5 animate-spin" />
              {analyze.isPending
                ? 'Đang phân tích dữ liệu...'
                : 'Đang nạp dự báo đã ghi nhận...'}
            </div>
          )}

          {/* Result */}
          {displayResult && !dangNap && (
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
                // id null khi chưa ghi nhận → dùng khóa bộ lọc để vẫn nạp lại đúng
                key={displayResult.forecast.id ?? `${filters.disease}|${filters.province}|${filters.month}`}
                currentMonth={targetMonthNum}
                currentYear={targetYearNum}
                diseaseLabel={displayResult.forecast.disease_label}
                regionFilter={filters.province}
              />
            </>
          )}
        </>
      )}

      {/* Kỳ này đã có dự báo ghi nhận trước đó — hỏi trước khi ghi đè */}
      {xacNhanGhiDe && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex items-start gap-3 px-5 py-4 border-b border-neutral-100">
              <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-neutral-900 mt-1.5">
                Đã có dự báo cho kỳ này
              </h3>
            </div>

            <div className="px-5 py-4">
              <p className="text-sm text-neutral-700">{xacNhanGhiDe}</p>
              <p className="text-xs text-neutral-500 mt-2">
                Ghi đè sẽ thay bản đã ghi nhận trước đó bằng kết quả vừa phân
                tích. Thao tác không hoàn tác được.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-neutral-100">
              <button
                type="button"
                onClick={() => setXacNhanGhiDe(null)}
                className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50"
              >
                Huỷ
              </button>
              <button
                type="button"
                onClick={() => ghiNhan(true)}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-amber-600 rounded-lg hover:bg-amber-700"
              >
                <Save className="w-4 h-4" />
                Ghi đè dự báo cũ
              </button>
            </div>
          </div>
        </div>
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
