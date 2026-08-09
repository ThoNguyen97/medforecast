import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, FileSpreadsheet, FileText, Eye } from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import {
  useConsumptionReport,
  useForecastAccuracyReport,
} from '../hooks/useReports';
import { useSupplyRequirementsSummary } from '../hooks/useSupplyRequirements';
import {
  useDiseaseOptions,
  useForecastHistory,
  useRegionOptions,
} from '../hooks/useForecastAnalysis';
import { useInventory } from '../hooks/useInventory';
import { epidemiologyService } from '../services/epidemiologyService';
import { reportsService } from '../services/reportsService';
import { supplyRecommendationService } from '../services/supplyRecommendationService';
import { SUPPLY_CATEGORY_LABELS } from '../utils/constants';
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

  // Data sources (chỉ fetch khi cần)
  const { data: diseases = [] } = useDiseaseOptions();
  const { data: regions = [] } = useRegionOptions();

  const consumption = useConsumptionReport(
    kind === 'inventory' || kind === 'shortage' || kind === 'procurement'
      ? {}
      : undefined,
  );

  const accuracy = useForecastAccuracyReport(
    kind === 'accuracy'
      ? {
          disease_type:
            filters.diseaseType !== 'all' ? filters.diseaseType : undefined,
        }
      : undefined,
  );

  const procurement = useQuery({
    queryKey: ['supply-recommendations', 'procurement-report', filters.category, filters.diseaseType],
    queryFn: () => {
      // Sử dụng cùng service như trang Alerts
      const currentDate = new Date();
      const forecastMonth = `${currentDate.getFullYear()}-${String(currentDate.getMonth() + 1).padStart(2, '0')}-01`;
      
      return supplyRecommendationService.calculateForMonth({
        forecast_month: forecastMonth,
        buffer_rate: 15, // Mặc định 15% như trang Alerts
      });
    },
    enabled: kind === 'procurement',
    retry: false,
    refetchOnWindowFocus: false,
  });

  const requirements = useSupplyRequirementsSummary(
    kind === 'shortage'
      ? {
          disease_type:
            filters.diseaseType !== 'all' ? filters.diseaseType : undefined,
        }
      : undefined,
  );

  const inventory = useInventory(
    kind === 'inventory' ? { limit: 2000 } : undefined,
  );

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

  const categoryOptions = useMemo(
    () =>
      Object.entries(SUPPLY_CATEGORY_LABELS).map(([key, label]) => ({
        key,
        label,
      })),
    [],
  );

  const filtersLabel = buildFiltersLabel(kind, filters, diseases);

  const [exporting, setExporting] = useState<'pdf' | 'excel' | null>(null);

  const handleExport = async (format: 'pdf' | 'excel') => {
    // Với procurement report, xuất Excel trực tiếp từ frontend
    if (kind === 'procurement' && format === 'excel') {
      await handleExportProcurementExcel();
      return;
    }
    
    try {
      setExporting(format);
      // Backend nhận 'forecast-accuracy' chứ không phải 'accuracy'
      const backendType = kind === 'accuracy' ? 'forecast-accuracy' : kind;
      const blob = await reportsService.exportReport({
        report_type: backendType as any,
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

  const handleExportProcurementExcel = async () => {
    try {
      setExporting('excel');
      
      // Import xlsx library
      const XLSX = await import('xlsx');
      
      // Lấy dữ liệu đã được filter (giống với màn hình)
      const previewData = buildProcurementPreview(procurement.data, filters.search);
      
      if (!previewData.sections || previewData.sections.length === 0) {
        alert('Không có dữ liệu để xuất');
        return;
      }
      
      const section = previewData.sections[0];
      
      // Tạo worksheet từ dữ liệu
      const wsData = [
        // Header row
        section.columns.map(col => col.label),
        // Data rows
        ...section.rows.map(row => 
          section.columns.map(col => row[col.key])
        ),
      ];
      
      const ws = XLSX.utils.aoa_to_sheet(wsData);
      
      // Set column widths
      ws['!cols'] = [
        { wch: 20 },  // Mã vật tư
        { wch: 40 },  // Tên vật tư
        { wch: 12 },  // ĐVT
        { wch: 16 },  // Nhu cầu dự báo
        { wch: 16 },  // Tồn hiện tại
        { wch: 18 },  // SL đề xuất nhập
      ];
      
      // Create workbook
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Đề xuất nhập kho');
      
      // Export to file
      const fileName = `de-xuat-nhap-kho-${new Date().toISOString().split('T')[0]}.xlsx`;
      XLSX.writeFile(wb, fileName);
      
    } catch (err) {
      console.error(err);
      alert('Không thể xuất Excel. Vui lòng thử lại.');
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
        return buildInventoryPreview(inventory.data ?? [], filters.status, filters.search);
      case 'shortage':
        return buildShortagePreview(requirements.data?.items ?? [], filters.search);
      case 'procurement':
        return buildProcurementPreview(procurement.data, filters.search);
      case 'accuracy':
        return buildAccuracyPreview(accuracy.data, forecastHistory.data ?? [], filters.search);
    }
  }, [
    kind,
    consumption.data,
    accuracy.data,
    requirements.data,
    inventory.data,
    forecastHistory.data,
    diseaseCases.data,
    procurement.data,
    filters.region,
    filters.status,
    filters.search,
    filters.startMonth,
    filters.endMonth,
  ]);

  const isLoading =
    (kind === 'inventory' && inventory.isLoading) ||
    (kind === 'shortage' && requirements.isLoading) ||
    (kind === 'procurement' && procurement.isLoading) ||
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
            Tổng hợp dữ liệu dịch tễ, tồn kho và đề xuất nhập kho. Chọn loại báo cáo
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
    const statusLabels: Record<string, string> = {
      normal: 'An toàn',
      low: 'Dưới ngưỡng',
      critical: 'Cần nhập gấp',
    };
    parts.push(statusLabels[f.status] ?? f.status);
  }
  return parts.join(' • ') || '—';
}

function formatMonth(monthStr: string): string {
  if (!monthStr) return '';
  const [year, month] = monthStr.split('-');
  return `${month}/${year}`;
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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
  startMonth?: string,
  endMonth?: string
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
          { key: 'risk_level', label: 'Mức nguy cơ' },
        ],
        rows: filtered.map((r) => ({
          month: `Tháng ${r.month}`,
          disease_label: r.disease_label,
          region: r.region || 'Toàn thành phố',
          predicted_cases: r.predicted_cases.toLocaleString('vi-VN'),
          risk_level: vietnameseRisk(r.risk_level),
        })),
      },
    ],
  };
}

function buildInventoryPreview(items: any[], statusFilter?: string, searchQuery?: string): PreviewBundle {
  // Helper function để classify status
  const classify = (cs: number, ss: number): 'normal' | 'low' | 'critical' => {
    if (ss <= 0) return 'normal';
    if (cs <= 0 || cs < ss * 0.3) return 'critical';
    if (cs <= ss) return 'low';
    return 'normal';
  };

  // Áp dụng filter theo status
  let filtered = items;
  if (statusFilter && statusFilter !== 'all') {
    filtered = items.filter((i) => {
      const cs = i.current_stock ?? 0;
      const ss = i.safety_stock ?? 0;
      return classify(cs, ss) === statusFilter;
    });
  }

  // Lọc theo thanh tìm kiếm
  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    filtered = filtered.filter((i) => {
      const name = (i.supply?.ten_hoat_chat || i.supply?.name || '').toLowerCase();
      const category = (SUPPLY_CATEGORY_LABELS[i.supply?.category] || i.supply?.category || '').toLowerCase();
      return name.includes(q) || category.includes(q);
    });
  }

  // Đếm theo trạng thái (từ items gốc, không filter)
  const safe = items.filter((i) => {
    const cs = i.current_stock ?? 0;
    const ss = i.safety_stock ?? 0;
    return classify(cs, ss) === 'normal';
  }).length;
  
  const low = items.filter((i) => {
    const cs = i.current_stock ?? 0;
    const ss = i.safety_stock ?? 0;
    return classify(cs, ss) === 'low';
  }).length;
  
  const critical = items.filter((i) => {
    const cs = i.current_stock ?? 0;
    const ss = i.safety_stock ?? 0;
    return classify(cs, ss) === 'critical';
  }).length;

  return {
    metrics: [
      { label: 'Tổng vật tư', value: items.length },
      { label: 'An toàn', value: safe, tone: 'success' },
      { label: 'Dưới ngưỡng', value: low, tone: 'warning' },
      { label: 'Cần nhập gấp', value: critical, tone: 'danger' },
    ],
    sections: [
      {
        title: 'Danh sách vật tư',
        columns: [
          { key: 'code', label: 'Mã vật tư' },
          { key: 'name', label: 'Tên vật tư' },
          { key: 'category', label: 'Loại' },
          { key: 'unit', label: 'ĐVT' },
          { key: 'current_stock', label: 'Tồn kho', align: 'right' },
          { key: 'safety_stock', label: 'Ngưỡng AT', align: 'right' },
        ],
        rows: filtered.map((i: any) => ({
          code: i.supply?.supply_code ?? '—',
          name: i.supply?.ten_hoat_chat ?? i.supply?.name ?? '—',
          category:
            SUPPLY_CATEGORY_LABELS[i.supply?.category] ??
            i.supply?.category ??
            '—',
          unit: i.supply?.unit ?? '—',
          current_stock: (i.current_stock ?? 0).toLocaleString('vi-VN'),
          safety_stock: (i.safety_stock ?? 0).toLocaleString('vi-VN'),
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
      { label: 'Số vật tư thiếu', value: shortageItems.length, tone: 'danger' },
      {
        label: 'Tổng lượng thiếu',
        value: totalShortage.toLocaleString('vi-VN'),
      },
    ],
    sections: [
      {
        title: 'Vật tư thiếu hụt',
        columns: [
          { key: 'name', label: 'Tên vật tư' },
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

function buildProcurementPreview(data: any, searchQuery?: string): PreviewBundle {
  if (!data || !data.items) {
    return {
      metrics: [
        { label: 'Số vật tư cần nhập', value: 0, tone: 'warning' },
        { label: 'Tổng số lượng đề xuất', value: 0 },
      ],
      sections: [],
    };
  }

  // Load manual thresholds từ sessionStorage (nếu có)
  let manualThresholds = new Map<number, number>();
  try {
    const saved = sessionStorage.getItem('manualThresholds');
    if (saved) {
      const parsed = JSON.parse(saved);
      manualThresholds = new Map(Object.entries(parsed).map(([k, v]) => [Number(k), v as number]));
    }
  } catch (e) {
    console.error('Failed to load manual thresholds:', e);
  }

  // Áp dụng manual thresholds và tính lại đề xuất nhập
  let items = data.items.map((item: any) => {
    const manualThreshold = manualThresholds.get(item.supply_id);
    if (manualThreshold !== undefined) {
      // Tính lại đề xuất nhập với ngưỡng AT mới
      const newSuggested = Math.max(0, manualThreshold - (item.current_stock ?? 0));
      return {
        ...item,
        safety_stock: manualThreshold,
        suggested_import: newSuggested,
      };
    }
    return item;
  });

  // Lọc theo thanh tìm kiếm
  if (searchQuery && searchQuery.trim()) {
    const q = searchQuery.toLowerCase();
    items = items.filter((i: any) => {
      const name = (i.ten_hoat_chat || '').toLowerCase();
      const code = (i.supply_code || '').toLowerCase();
      const group = (i.group_name || '').toLowerCase();
      return name.includes(q) || code.includes(q) || group.includes(q);
    });
  }

  // Chỉ lấy các vật tư cần nhập (suggested_import > 0)
  const needImportItems = items.filter((i: any) => (i.suggested_import ?? 0) > 0);
  const totalOrder = needImportItems.reduce((acc: number, i: any) => acc + (i.suggested_import ?? 0), 0);

  return {
    metrics: [
      { label: 'Số vật tư cần nhập', value: needImportItems.length, tone: 'warning' },
      {
        label: 'Tổng số lượng đề xuất',
        value: totalOrder,
      },
    ],
    sections: [
      {
        title: 'Đề xuất nhập kho',
        columns: [
          { key: 'code', label: 'Mã vật tư' },
          { key: 'name', label: 'Tên vật tư' },
          { key: 'unit', label: 'ĐVT' },
          { key: 'demand', label: 'Nhu cầu dự báo', align: 'right' },
          { key: 'stock', label: 'Tồn hiện tại', align: 'right' },
          { key: 'recommended', label: 'SL đề xuất nhập', align: 'right' },
        ],
        rows: needImportItems.map((i: any) => ({
          code: i.supply_code || '—',
          name: i.ten_hoat_chat || '—',
          unit: i.unit ?? '',
          demand: (i.predicted_need_total ?? 0).toLocaleString('vi-VN'),
          stock: (i.current_stock ?? 0).toLocaleString('vi-VN'),
          recommended: (i.suggested_import ?? 0).toLocaleString('vi-VN'),
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
