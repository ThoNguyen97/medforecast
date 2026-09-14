import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, FileSpreadsheet, FileText, Eye } from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { useForecastAccuracyReport } from '../hooks/useReports';
import { useSupplyRequirementsSummary } from '../hooks/useSupplyRequirements';
import {
  useDiseaseOptions,
  useForecastHistory,
  useRegionOptions,
} from '../hooks/useForecastAnalysis';
import { dssService } from '../services/dssService';
import { epidemiologyService } from '../services/epidemiologyService';
import { triggerDownload } from '../utils/download';
import { reportsService } from '../services/reportsService';
import { LEVEL_LABELS, type AlertLevel, type AlertRow } from '../types/dashboardV2';
import ReportTypePicker, {
  type ReportKind,
} from '../components/reports/ReportTypePicker';
import ReportFilterPanel, {
  type ReportFilterState,
} from '../components/reports/ReportFilterPanel';
import ReportPreview from '../components/reports/ReportPreview';

/** Module 8 — Báo cáo */
export default function Reports() {
  const { setPageTitle } = useUIStore();
  useEffect(() => {
    setPageTitle('Báo cáo');
  }, [setPageTitle]);

  const [kind, setKind] = useState<ReportKind>('epidemic');
  const [filters, setFilters] = useState<ReportFilterState>({
    search: '',
    startMonth: '',
    endMonth: '',
    diseaseType: 'all',
    region: 'all',
    category: 'all',
    status: 'all',
  });

  // Nguồn dữ liệu — mỗi hook chỉ gọi API khi loại báo cáo đang chọn cần nó
  // (không bắn 5 request mỗi lần mở trang).
  const { data: diseases = [] } = useDiseaseOptions();
  const { data: regions = [] } = useRegionOptions();

  const accuracy = useForecastAccuracyReport(
    {
      disease_type: filters.diseaseType !== 'all' ? filters.diseaseType : undefined,
    },
    { enabled: kind === 'accuracy' },
  );

  const requirements = useSupplyRequirementsSummary(
    { disease_type: filters.diseaseType !== 'all' ? filters.diseaseType : undefined },
    { enabled: kind === 'shortage' },
  );

  // Báo cáo Tồn kho thuốc đọc CÙNG chuỗi DOI với trang Quản lý thuốc / Cảnh
  // báo (toàn danh mục, 1 lần, lọc client). Trước 13/09/2026 nó đọc /inventory
  // và xếp loại theo safety_stock — hệ nhãn thứ hai mâu thuẫn trang Cảnh báo.
  const inventory = useQuery({
    queryKey: ['dss', 'alerts', 'report-inventory'],
    queryFn: () => dssService.getAlerts({ focus: false, level: null, limit: 2000, offset: 0 }),
    enabled: kind === 'inventory',
    staleTime: 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  });

  const forecastHistory = useForecastHistory(
    kind === 'forecast' || kind === 'accuracy'
      ? {
          limit: 1000,
          disease_type:
            filters.diseaseType !== 'all' ? filters.diseaseType : undefined,
          region: filters.region !== 'all' ? filters.region : undefined,
          start_date: filters.startMonth ? `${filters.startMonth}-01` : undefined,
          end_date: filters.endMonth ? (() => {
            const endDate = new Date(filters.endMonth + '-01');
            endDate.setMonth(endDate.getMonth() + 1);
            endDate.setDate(0); // Last day of the month
            return endDate.toISOString().split('T')[0];
          })() : undefined,
        }
      : undefined,
    { enabled: kind === 'forecast' || kind === 'accuracy' },
  );

  // Báo cáo "Tình hình dịch bệnh" lấy SỐ CA THẬT từ disease_cases (đã import),
  // không phải từ bảng dự báo.
  const diseaseCases = useQuery({
    queryKey: ['report-disease-cases', filters.diseaseType, filters.region, filters.startMonth, filters.endMonth],
    queryFn: () => {
      // Convert month filters to date range
      const params: any = {
        limit: 50000,
        disease_type:
          filters.diseaseType !== 'all'
            ? (filters.diseaseType as any)
            : undefined,
        location: filters.region !== 'all' ? filters.region : undefined,
      };

      // Add date range if months are specified
      if (filters.startMonth) {
        params.start_date = `${filters.startMonth}-01`;
      }
      if (filters.endMonth) {
        // Set to last day of end month
        const endDate = new Date(filters.endMonth + '-01');
        endDate.setMonth(endDate.getMonth() + 1);
        endDate.setDate(0); // Last day of previous month
        params.end_date = endDate.toISOString().split('T')[0];
      }

      return epidemiologyService.getDiseaseCases(params);
    },
    enabled: kind === 'epidemic',
    retry: false,
    refetchOnWindowFocus: false,
  });

  const filtersLabel = buildFiltersLabel(kind, filters, diseases);

  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);

  const handleExport = async (format: 'pdf' | 'excel') => {
    try {
      setExporting(format);
      // Backend nhận 'forecast-accuracy' chứ không phải 'accuracy'
      const backendType = kind === 'accuracy' ? 'forecast-accuracy' : kind;
      const blob = await reportsService.exportReport({
        report_type: backendType,
        format,
        disease_type:
          filters.diseaseType !== 'all' ? filters.diseaseType : undefined,
        location: filters.region !== 'all' ? filters.region : undefined,
      } as any);
      const ext = format === 'pdf' ? 'pdf' : 'xlsx';
      triggerDownload(blob, `${kind}-report.${ext}`);
    } catch (err) {
      console.error(err);
      alert('Không thể xuất báo cáo. Vui lòng thử lại.');
    } finally {
      setExporting(null);
    }
  };

  // Build preview metrics + sections theo từng loại
  const preview = useMemo(() => {
    switch (kind) {
      case 'epidemic':
        return buildEpidemicPreview(diseaseCases.data ?? []);
      case 'forecast':
        return buildForecastPreview(
          forecastHistory.data ?? [],
          filters.region,
          filters.startMonth,
          filters.endMonth,
        );
      case 'inventory':
        return buildInventoryPreview(inventory.data?.rows ?? [], filters.status, filters.search);
      case 'shortage':
        return buildShortagePreview(requirements.data?.items ?? [], filters.search);
      case 'accuracy':
        return buildAccuracyPreview(accuracy.data, forecastHistory.data ?? [], filters.search);
    }
  }, [
    kind,
    accuracy.data,
    requirements.data,
    inventory.data,
    forecastHistory.data,
    diseaseCases.data,
    filters.region,
    filters.status,
    filters.search,
    filters.startMonth,
    filters.endMonth,
  ]);

  const isLoading =
    (kind === 'inventory' && inventory.isLoading) ||
    (kind === 'shortage' && requirements.isLoading) ||
    (kind === 'accuracy' && accuracy.isLoading) ||
    (kind === 'forecast' && forecastHistory.isLoading) ||
    (kind === 'epidemic' && diseaseCases.isLoading);

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">Báo cáo</h2>
          <p className="text-sm text-neutral-500 mt-1">
            Tổng hợp dữ liệu dịch tễ, dự báo, tồn kho và thiếu hụt. Chọn loại báo cáo
            rồi cấu hình bộ lọc để xem trước & xuất file.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={() => handleExport('excel')}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-neutral-200 rounded-xl text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Xuất Excel
          </button>
          <button
            type="button"
            onClick={() => handleExport('pdf')}
            disabled={exporting === 'pdf'}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {exporting === 'pdf' ? (
              <Download className="w-4 h-4 animate-pulse" />
            ) : (
              <FileText className="w-4 h-4" />
            )}
            Xuất PDF
          </button>
        </div>
      </div>

      {/* Step 1: chọn loại báo cáo */}
      <Section step="1" title="Chọn loại báo cáo">
        <ReportTypePicker active={kind} onSelect={setKind} />
      </Section>

      {/* Step 2: bộ lọc */}
      <Section step="2" title="Cấu hình bộ lọc">
        <ReportFilterPanel
          kind={kind}
          state={filters}
          onChange={setFilters}
          diseases={diseases}
          regions={regions}
        />
      </Section>

      {/* Step 3: preview */}
      <Section step="3" title="Xem trước báo cáo" icon={<Eye className="w-4 h-4" />}>
        <ReportPreview
          kind={kind}
          isLoading={isLoading}
          isEmpty={!isLoading && preview.metrics.length === 0 && preview.sections.length === 0}
          metrics={preview.metrics}
          sections={preview.sections}
          generatedAt={new Date().toLocaleString('vi-VN')}
          periodLabel=""
          filtersLabel={filtersLabel}
        />
      </Section>
    </div>
  );
}

// ── Section wrapper ─────────────────────────────────────────────────────────

function Section({
  step,
  title,
  icon,
  children,
}: {
  step: string;
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-[11px] font-bold">
          {step}
        </span>
        <h3 className="text-sm font-semibold text-neutral-900">{title}</h3>
        {icon && <span className="text-neutral-400 ml-1">{icon}</span>}
      </div>
      {children}
    </section>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function buildFiltersLabel(
  kind: ReportKind,
  f: ReportFilterState,
  diseases: { key: string; label: string }[],
): string {
  const parts: string[] = [];
  
  // Thêm search query nếu có (cho các báo cáo không sử dụng month filters)
  if (kind !== 'epidemic' && kind !== 'forecast' && f.search && f.search.trim()) {
    parts.push(`"${f.search.trim()}"`);
  }
  
  // Thêm thông tin tháng cho epidemic và forecast
  if ((kind === 'epidemic' || kind === 'forecast') && (f.startMonth || f.endMonth)) {
    if (f.startMonth && f.endMonth) {
      parts.push(`${formatMonth(f.startMonth)} → ${formatMonth(f.endMonth)}`);
    } else if (f.startMonth) {
      parts.push(`Từ ${formatMonth(f.startMonth)}`);
    } else if (f.endMonth) {
      parts.push(`Đến ${formatMonth(f.endMonth)}`);
    }
  }
  
  if (['epidemic', 'forecast', 'accuracy'].includes(kind)) {
    const d =
      f.diseaseType === 'all'
        ? 'Tất cả bệnh'
        : diseases.find((x) => x.key === f.diseaseType)?.label ?? f.diseaseType;
    parts.push(d);
  }
  if (['epidemic', 'forecast'].includes(kind)) {
    parts.push(f.region === 'all' ? 'Toàn thành phố' : f.region);
  }
  if (kind === 'inventory' && f.status !== 'all') {
    parts.push(LEVEL_LABELS[f.status as AlertLevel] ?? f.status);
  }
  return parts.join(' • ') || '—';
}

function formatMonth(monthStr: string): string {
  if (!monthStr) return '';
  const [year, month] = monthStr.split('-');
  return `${month}/${year}`;
}

// ── Preview builders cho từng loại ──────────────────────────────────────────

interface PreviewBundle {
  metrics: Array<{
    label: string;
    value: string | number;
    hint?: string;
    tone?: 'default' | 'success' | 'warning' | 'danger';
  }>;
  sections: Array<{
    title: string;
    columns: { key: string; label: string; align?: 'left' | 'right' }[];
    rows: Array<Record<string, string | number>>;
  }>;
}

function buildEpidemicPreview(
  cases: any[],
): PreviewBundle {
  const totalActual = cases.reduce(
    (acc, c) => acc + (c.case_count ?? 0),
    0,
  );
  const monthsCovered = new Set(
    cases.map((c) => (c.recorded_at ?? '').slice(0, 7)),
  ).size;
  const diseasesCount = new Set(cases.map((c) => c.icd_code)).size;

  const monthLabel = (iso: string) => {
    const d = new Date(iso);
    return `${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
  };

  // Sắp xếp mới nhất trước
  const sorted = [...cases].sort(
    (a, b) =>
      new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime(),
  );

  return {
    metrics: [
      {
        label: 'Tổng ca thực tế',
        value: totalActual.toLocaleString('vi-VN'),
        hint: `Trong ${monthsCovered} tháng`,
      },
      { label: 'Số tháng có dữ liệu', value: monthsCovered },
      { label: 'Số bệnh được ghi nhận', value: diseasesCount },
    ],
    sections: [
      {
        title: 'Chi tiết theo tháng',
        columns: [
          { key: 'month', label: 'Tháng' },
          { key: 'disease_label', label: 'Bệnh' },
          { key: 'region', label: 'Khu vực' },
          { key: 'actual_cases', label: 'Số ca thực tế', align: 'right' },
        ],
        rows: sorted.map((c) => ({
          month: `Tháng ${monthLabel(c.recorded_at)}`,
          disease_label: c.disease_name || c.icd_code,
          region: c.location || '—',
          actual_cases: (c.case_count ?? 0).toLocaleString('vi-VN'),
        })),
      },
    ],
  };
}

function buildForecastPreview(
  history: any[], 
  selectedRegion?: string, 
  _startMonth?: string,
  _endMonth?: string
): PreviewBundle {
  // Lọc theo region được chọn
  let filtered = history;
  if (!selectedRegion || selectedRegion === 'all') {
    // Nếu chọn "Tất cả" → chỉ lấy dự báo toàn quốc để tránh đếm trùng
    filtered = history.filter((r) => 
      !r.region || r.region === 'Toàn thành phố' || r.region === 'Toàn quốc'
    );
  } else {
    // Nếu chọn khu vực cụ thể → lấy đúng khu vực đó
    filtered = history.filter((r) => r.region === selectedRegion);
  }
  
  // Note: Date filtering đã được xử lý ở backend level qua API call
  // Không cần client-side filtering cho date nữa
  
  const total = filtered.reduce((acc, r) => acc + (r.predicted_cases ?? 0), 0);
  const high = filtered.filter((r) => r.risk_level === 'high' || r.risk_level === 'very_high')
    .length;

  return {
    metrics: [
      {
        label: 'Tổng số ca dự báo',
        value: total.toLocaleString('vi-VN'),
        hint: !selectedRegion || selectedRegion === 'all' ? 'Toàn thành phố' : selectedRegion,
      },
      {
        label: 'Số kỳ dự báo',
        value: filtered.length,
      },
      {
        label: 'Mức nguy cơ cao trở lên',
        value: high,
        tone: high > 0 ? 'danger' : 'default',
      },
    ],
    sections: [
      {
        title: 'Chi tiết dự báo',
        columns: [
          { key: 'month', label: 'Tháng' },
          { key: 'disease_label', label: 'Bệnh' },
          { key: 'region', label: 'Khu vực' },
          { key: 'predicted_cases', label: 'Số ca dự báo', align: 'right' },
          { key: 'actual_cases', label: 'Số ca thực tế', align: 'right' },
          { key: 'deviation_pct', label: 'Độ lệch', align: 'right' },
          { key: 'risk_level', label: 'Mức nguy cơ' },
        ],
        rows: filtered.map((r) => ({
          month: `Tháng ${r.month}`,
          disease_label: r.disease_label,
          region: r.region || 'Toàn thành phố',
          predicted_cases: r.predicted_cases.toLocaleString('vi-VN'),
          actual_cases:
            r.actual_cases !== null && r.actual_cases !== undefined
              ? r.actual_cases.toLocaleString('vi-VN')
              : '—',
          deviation_pct:
            r.deviation_pct !== null && r.deviation_pct !== undefined
              ? `${r.deviation_pct > 0 ? '+' : ''}${r.deviation_pct.toFixed(1)}%`
              : '—',
          risk_level: vietnameseRisk(r.risk_level),
        })),
      },
    ],
  };
}

function buildInventoryPreview(rows: AlertRow[], statusFilter?: string, searchQuery?: string): PreviewBundle {
  const fmt = (v: number | null | undefined, digits = 0) =>
    v == null ? '—' : v.toLocaleString('vi-VN', { maximumFractionDigits: digits });

  let filtered = rows;
  if (statusFilter && statusFilter !== 'all') {
    filtered = filtered.filter((r) => r.muc === statusFilter);
  }
  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter(
      (r) =>
        r.supply_code.toLowerCase().includes(q) ||
        (r.ten || '').toLowerCase().includes(q) ||
        (r.danh_muc || '').toLowerCase().includes(q),
    );
  }

  const dem = (lv: AlertLevel) => rows.filter((r) => r.muc === lv).length;

  return {
    metrics: [
      { label: 'Tổng thuốc', value: rows.length },
      { label: 'Đỏ', value: dem('red'), tone: 'danger' },
      { label: 'Vàng', value: dem('amber'), tone: 'warning' },
      { label: 'Xanh', value: dem('green'), tone: 'success' },
      { label: 'Xám', value: dem('grey') },
    ],
    sections: [
      {
        title: 'Tồn kho thuốc theo DOI',
        columns: [
          { key: 'code', label: 'Mã' },
          { key: 'name', label: 'Thuốc' },
          { key: 'category', label: 'Danh mục' },
          { key: 'unit', label: 'ĐVT' },
          { key: 'stock', label: 'Tồn kho', align: 'right' },
          { key: 'usable', label: 'Tồn hữu dụng', align: 'right' },
          { key: 'd_daily', label: 'Tiêu hao/ngày', align: 'right' },
          { key: 'doi', label: 'DOI (ngày)', align: 'right' },
          { key: 'status', label: 'Nhãn' },
        ],
        rows: filtered.map((r) => ({
          code: r.supply_code,
          name: r.ten || r.supply_code,
          category: r.danh_muc || 'Khác',
          unit: r.don_vi ?? '—',
          stock: fmt(r.s_total),
          usable: fmt(r.s_usable),
          d_daily: fmt(r.d_daily, 2),
          doi: fmt(r.doi, 1),
          status: LEVEL_LABELS[r.muc],
        })),
      },
    ],
  };
}

function buildShortagePreview(items: any[], searchQuery?: string): PreviewBundle {
  let shortageItems = items.filter((i) => (i.shortage_amount ?? 0) > 0);
  
  // Lọc theo thanh tìm kiếm
  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    shortageItems = shortageItems.filter((i) => {
      const name = (i.supply_name || '').toLowerCase();
      return name.includes(q);
    });
  }
  
  const totalShortage = shortageItems.reduce(
    (acc, i) => acc + (i.shortage_amount ?? 0),
    0,
  );

  return {
    metrics: [
      { label: 'Số thuốc thiếu', value: shortageItems.length, tone: 'danger' },
      {
        label: 'Tổng lượng thiếu',
        value: totalShortage.toLocaleString('vi-VN'),
      },
    ],
    sections: [
      {
        title: 'Thuốc thiếu hụt',
        columns: [
          { key: 'name', label: 'Tên thuốc' },
          { key: 'unit', label: 'ĐVT' },
          { key: 'demand', label: 'Nhu cầu', align: 'right' },
          { key: 'stock', label: 'Tồn kho', align: 'right' },
          { key: 'shortage', label: 'Mức thiếu', align: 'right' },
        ],
        rows: shortageItems.map((i: any) => ({
          name: i.supply_name,
          unit: i.supply_unit ?? '',
          demand: (i.total_required_quantity ?? 0).toLocaleString('vi-VN'),
          stock: (i.current_stock ?? 0).toLocaleString('vi-VN'),
          shortage: (i.shortage_amount ?? 0).toLocaleString('vi-VN'),
        })),
      },
    ],
  };
}

function buildAccuracyPreview(_accuracy: any, history: any[], searchQuery?: string): PreviewBundle {
  let withActual = history.filter((r) => r.deviation_pct !== null);
  
  // Lọc theo thanh tìm kiếm
  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    withActual = withActual.filter((r) => {
      const diseaseName = (r.disease_label || '').toLowerCase();
      return diseaseName.includes(q);
    });
  }
  
  const avgDeviation =
    withActual.length === 0
      ? 0
      : withActual.reduce((acc, r) => acc + Math.abs(r.deviation_pct ?? 0), 0) /
        withActual.length;

  return {
    metrics: [
      { label: 'Số kỳ đã đối chiếu', value: withActual.length },
      {
        label: 'Sai số trung bình',
        value: `${avgDeviation.toFixed(1)}%`,
        tone: avgDeviation <= 10 ? 'success' : avgDeviation <= 20 ? 'warning' : 'danger',
      },
    ],
    sections: [
      {
        title: 'So sánh dự báo vs thực tế',
        columns: [
          { key: 'month', label: 'Tháng' },
          { key: 'disease_label', label: 'Bệnh' },
          { key: 'predicted_cases', label: 'Dự báo', align: 'right' },
          { key: 'actual_cases', label: 'Thực tế', align: 'right' },
          { key: 'deviation', label: 'Độ lệch', align: 'right' },
        ],
        rows: withActual.map((r: any) => ({
          month: `Tháng ${r.month}`,
          disease_label: r.disease_label,
          predicted_cases: r.predicted_cases.toLocaleString('vi-VN'),
          actual_cases:
            r.actual_cases !== null
              ? r.actual_cases.toLocaleString('vi-VN')
              : '—',
          deviation: `${r.deviation_pct > 0 ? '+' : ''}${r.deviation_pct.toFixed(1)}%`,
        })),
      },
    ],
  };
}

function vietnameseRisk(level?: string): string {
  const map: Record<string, string> = {
    low: 'Thấp',
    medium: 'Trung bình',
    high: 'Cao',
    very_high: 'Rất cao',
  };
  return map[level ?? ''] ?? '—';
}
