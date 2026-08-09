import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Calendar,
  MapPin,
  Building2,
  Search,
  Download,
  Upload,
  Plus,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  X,
  Edit3,
  Trash2,
  Cloud,
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
} from 'recharts';
import { SERIES, INK, gridProps, tooltipStyle } from '../utils/chartTheme';
import { useUIStore } from '../store/uiStore';
import api from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { VN_PROVINCES, VN_PROVINCES_SET, getDistrictsForRegion, normalizeProvinceName } from '../utils/vietnamRegions';

const PAGE_SIZE = 5;

interface EnvRow {
  id: number;
  recorded_at: string;
  location: string;
  district_ward?: string | null;
  temperature?: number | null;
  humidity?: number | null;
  rainfall?: number | null;
  air_quality_index?: number | null;
  pm25?: number | null;
}

interface TrendPoint {
  year: number;
  temp: number | null;
  humidity: number | null;
  rainfall: number | null;
  aqi: number | null;
  pm25: number | null;
}

interface ImportError {
  row: number;
  reason: string;
}

export default function Weather() {
  const { setPageTitle } = useUIStore();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [items, setItems] = useState<EnvRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [syncingOpenMeteo, setSyncingOpenMeteo] = useState(false);

  // Filters
  const [filterYear, setFilterYear] = useState<string>(() =>
    new Date().getFullYear().toString(),
  );
  const [filterMonth, setFilterMonth] = useState<string>('all');
  const [filterProvince, setFilterProvince] = useState<string>('all');
  const [provinces, setProvinces] = useState<string[]>([]);
  // Map cascade tỉnh → list quận đã có data trong DB
  const [provinceDistricts, setProvinceDistricts] = useState<Record<string, string[]>>({});

  // Pagination
  const [page, setPage] = useState(1);

  // Trend chart
  const [trend, setTrend] = useState<TrendPoint[]>([]);

  // Form modal
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<EnvRow | null>(null);
  const [form, setForm] = useState({
    month: new Date().toISOString().slice(0, 7),
    province: 'TP. Hồ Chí Minh',
    district: '',
    temp: 30,
    humidity: 75,
    rainfall: 0,
    aqi: 0,
    pm25: 0,
  });
  const [formError, setFormError] = useState<string>('');

  // Import result modal
  const [importResult, setImportResult] = useState<{
    imported: number;
    updated: number;
    skipped: number;
    errors: ImportError[];
    truncated: boolean;
  } | null>(null);

  useEffect(() => {
    setPageTitle('Quản Lý Dữ Liệu Thời Tiết');
    loadData();
    loadDistinctValues();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadTrend();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterYear, filterMonth, filterProvince]);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await api.get('/environmental/', { params: { limit: 50000 } });
      setItems(res.data || []);
    } catch (err: any) {
      console.error('❌ Environmental API Error:', err);
      console.error('Response:', err.response?.data);
      console.error('Status:', err.response?.status);
    } finally {
      setLoading(false);
    }
  };

  const loadDistinctValues = async () => {
    try {
      // Merge admin.regions + DB lịch sử + master VN
      const [adminRes, distinctRes] = await Promise.all([
        api.get('/admin/regions').catch(() => ({ data: [] as any[] })),
        api.get('/environmental/distinct-values').catch(() => ({
          data: { provinces: [], districts: [], province_districts: {} },
        })),
      ]);

      const adminNames: string[] = (adminRes.data || []).map((r: any) => r.name);
      const adminProvinces: string[] = Array.from(
        new Set(
          (adminRes.data || [])
            .map((r: any) => r.province)
            .filter((v: any) => typeof v === 'string' && v),
        ),
      );

      const dbProvinces: string[] = distinctRes.data?.provinces ?? [];
      const dbDistricts: string[] = distinctRes.data?.districts ?? [];
      const dbCascade: Record<string, string[]> =
        distinctRes.data?.province_districts ?? {};

      // Province dropdown: chỉ giữ các giá trị thực sự là tỉnh
      // Chuẩn hoá tên ("Thành phố Hồ Chí Minh" → "TP. Hồ Chí Minh") trước khi so master.
      const LEGACY_ALLOW = new Set(['Toàn thành phố']);
      const extraFromAdminDb = [...adminProvinces, ...dbProvinces]
        .map((n) => normalizeProvinceName(n))
        .filter((n) => VN_PROVINCES_SET.has(n) || LEGACY_ALLOW.has(n));
      const merged = Array.from(
        new Set<string>([...VN_PROVINCES, ...extraFromAdminDb]),
      );
      const final = merged.filter((p) => p !== 'Toàn thành phố');
      if (merged.includes('Toàn thành phố')) final.unshift('Toàn thành phố');
      setProvinces(final);

      // Cho dropdown khi chưa chọn tỉnh — gộp tất cả admin districts + DB
      const mergedDistricts = Array.from(
        new Set([...adminNames, ...dbDistricts]),
      ).filter(Boolean);
      mergedDistricts.sort((a, b) => {
        if (a === 'Toàn thành phố') return -1;
        if (b === 'Toàn thành phố') return 1;
        return a.localeCompare(b, 'vi');
      });
      setDistricts(mergedDistricts);

      // Chuẩn hoá key cascade để khớp value dropdown (master)
      const normCascade: Record<string, string[]> = {};
      for (const [prov, dists] of Object.entries(dbCascade)) {
        const key = normalizeProvinceName(prov);
        normCascade[key] = Array.from(
          new Set([...(normCascade[key] ?? []), ...(dists as string[])]),
        );
      }
      setProvinceDistricts(normCascade);
    } catch {
      /* ignore */
    }
  };

  const loadTrend = async () => {
    try {
      // Use selected month for trend, or default to current month if "all" is selected
      const month = filterMonth !== 'all' 
        ? Number(filterMonth) 
        : new Date().getMonth() + 1;
      
      const res = await api.get('/environmental/trend', {
        params: {
          target_month: month,
          province: filterProvince !== 'all' ? filterProvince : undefined,
          // Don't filter by district for trend - use province-level data
          // district: filterDistrict !== 'all' ? filterDistrict : undefined,
        },
      });
      setTrend(res.data || []);
    } catch {
      setTrend([]);
    }
  };

  // Filter and paginate - show all months of selected year, optionally filter by specific month
  const filtered = useMemo(() => {
    console.log('🔍 Weather Filter Debug:', {
      totalItems: items.length,
      filterYear,
      filterMonth, 
      filterProvince,
      sampleItem: items[0]
    });
    
    return items.filter((it) => {
      // Filter by year
      if (filterYear) {
        const year = it.recorded_at?.slice(0, 4);
        if (year !== filterYear) return false;
      }
      // Filter by specific month if selected (not 'all')
      if (filterMonth !== 'all') {
        const month = it.recorded_at?.slice(5, 7);
        if (month !== filterMonth) return false;
      }
      // Filter by province
      if (filterProvince !== 'all' && normalizeProvinceName(it.location) !== normalizeProvinceName(filterProvince)) return false;
      
      return true;
    });
  }, [items, filterYear, filterMonth, filterProvince]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * PAGE_SIZE;
  const paged = filtered.slice(startIdx, startIdx + PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [filtered.length]);

  // Actions
  const downloadTemplate = () => {
    window.open(`${api.defaults.baseURL}/environmental/template`, '_blank');
  };

  const handleImportCSV = async (file: File) => {
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/environmental/import-csv', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const d = res.data ?? {};
      setImportResult({
        imported: d.imported ?? 0,
        updated: d.updated ?? 0,
        skipped: d.skipped ?? 0,
        errors: (d.errors ?? []) as ImportError[],
        truncated: !!d.errors_truncated,
      });
      loadData();
      loadDistinctValues();
    } catch (err: any) {
      alert('Lỗi import: ' + (err.response?.data?.detail || err.message));
    } finally {
      setImporting(false);
    }
  };

  const syncOpenMeteo = async () => {
    const province =
      filterProvince !== 'all' ? filterProvince : 'TP. Hồ Chí Minh';
    if (
      !window.confirm(
        `Đồng bộ dữ liệu thời tiết từ Open-Meteo cho "${province}" (10 năm quá khứ + 16 ngày dự báo)?`,
      )
    ) {
      return;
    }
    setSyncingOpenMeteo(true);
    try {
      const res = await api.post('/environmental/sync-openmeteo', null, {
        params: { province, months_back: 120, forecast_days: 16 },
      });
      const d = res.data ?? {};
      alert(
        `✓ Open-Meteo sync xong cho ${d.province}\n` +
          `Mới: ${d.imported}, cập nhật: ${d.updated}, tổng ${d.total_months} tháng.\n` +
          `(historical ${d.historical_days} ngày · forecast ${d.forecast_days} ngày · AQI ${d.air_quality_days} ngày)`,
      );
      loadData();
      loadDistinctValues();
      loadTrend();
    } catch (err: any) {
      alert('Lỗi sync Open-Meteo: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSyncingOpenMeteo(false);
    }
  };

  const openAddForm = () => {
    setEditing(null);
    setForm({
      month: new Date().toISOString().slice(0, 7),
      province: 'TP. Hồ Chí Minh',
      district: '',
      temp: 30,
      humidity: 75,
      rainfall: 0,
      aqi: 0,
      pm25: 0,
    });
    setFormError('');
    setShowForm(true);
  };

  const openEditForm = (row: EnvRow) => {
    setEditing(row);
    setForm({
      month: row.recorded_at.slice(0, 7),
      province: row.location,
      district: row.district_ward ?? '',
      temp: Number(row.temperature) || 0,
      humidity: Number(row.humidity) || 0,
      rainfall: Number(row.rainfall) || 0,
      aqi: Number(row.air_quality_index) || 0,
      pm25: Number(row.pm25) || 0,
    });
    setFormError('');
    setShowForm(true);
  };

  const validate = (): string => {
    if (!form.month) return 'Tháng/Năm không được để trống';
    if (!form.province.trim()) return 'Tỉnh/Thành phố không được để trống';
    if (form.temp < 10 || form.temp > 45) return 'Nhiệt độ phải từ 10°C đến 45°C';
    if (form.humidity < 0 || form.humidity > 100) return 'Độ ẩm phải từ 0% đến 100%';
    if (form.rainfall < 0) return 'Lượng mưa không được âm';
    if (form.aqi < 0) return 'AQI không được âm';
    if (form.pm25 < 0) return 'PM2.5 không được âm';
    return '';
  };

  const submitForm = async () => {
    const err = validate();
    if (err) {
      setFormError(err);
      return;
    }
    setFormError('');
    try {
      const isoDate = new Date(`${form.month}-01`).toISOString();
      const payload = {
        recorded_at: isoDate,
        location: form.province,
        district_ward: form.district || null,
        temperature: form.temp,
        humidity: form.humidity,
        rainfall: form.rainfall,
        air_quality_index: form.aqi,
        pm25: form.pm25,
        data_source: 'manual',
      };
      if (editing) {
        // Spec 4.2 #3: PUT để giữ id + created_at
        await api.put(`/environmental/${editing.id}`, payload);
      } else {
        await api.post('/environmental/', payload);
      }
      setShowForm(false);
      loadData();
      loadDistinctValues();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
          ? detail.map((d: any) => d.msg).join(', ')
          : detail?.message || e.message || 'Lỗi không xác định';
      setFormError(msg);
    }
  };

  const deleteRow = async (id: number) => {
    if (!window.confirm('Xoá bản ghi?')) return;
    try {
      await api.delete(`/environmental/${id}`);
      loadData();
    } catch (err: any) {
      alert('Lỗi: ' + err.message);
    }
  };

  const formatMonthLabel = () => {
    const monthName = filterMonth !== 'all' 
      ? `tháng ${Number(filterMonth)}`
      : 'các tháng trong năm';
    return `${monthName} (qua các năm)`;
  };

  const aqiColor = (v?: number | null) => {
    if (v == null) return 'text-neutral-700';
    if (v >= 150) return 'text-red-600 font-bold';
    if (v >= 100) return 'text-amber-600 font-bold';
    if (v >= 50) return 'text-yellow-600';
    return 'text-emerald-600';
  };

  const pm25Color = (v?: number | null) => {
    if (v == null) return 'text-neutral-700';
    if (v >= 35) return 'text-red-600 font-bold';
    if (v >= 25) return 'text-amber-600';
    return 'text-emerald-600';
  };

  return (
    <div className="space-y-6">
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleImportCSV(f);
          if (e.target) e.target.value = '';
        }}
      />

      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">
            Dữ liệu thời tiết & môi trường
          </h2>
          <p className="text-sm text-neutral-500 mt-1">
            Lưu trữ và quản lý các chỉ số nhiệt độ, độ ẩm, lượng mưa và chất lượng không khí
            theo khu vực.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={downloadTemplate}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm font-medium hover:bg-neutral-50"
          >
            <Download className="w-4 h-4" /> Tải file mẫu
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm font-medium hover:bg-neutral-50 disabled:opacity-50"
          >
            <Upload className="w-4 h-4" />
            {importing ? 'Đang import…' : 'Import Excel/CSV'}
          </button>
          <button
            onClick={syncOpenMeteo}
            disabled={syncingOpenMeteo}
            className="inline-flex items-center gap-2 px-4 py-2 bg-sky-50 border border-sky-200 text-sky-700 rounded-xl text-sm font-medium hover:bg-sky-100 disabled:opacity-50"
            title="Đồng bộ dữ liệu thời tiết và AQI từ Open-Meteo (free, no API key)"
          >
            <Cloud className="w-4 h-4" />
            {syncingOpenMeteo ? 'Đang đồng bộ…' : 'Đồng bộ Open-Meteo'}
          </button>
          <button
            onClick={openAddForm}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" /> Thêm dữ liệu mới
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl border border-neutral-200 p-5">
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 items-end">
          <div>
            <label className="block text-sm font-medium text-neutral-600 mb-1.5">Năm</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <select
                value={filterYear}
                onChange={(e) => setFilterYear(e.target.value)}
                className="w-full pl-9 pr-9 py-2 border border-neutral-200 rounded-lg text-sm appearance-none bg-white"
              >
                {Array.from({ length: 10 }, (_, i) => {
                  const year = new Date().getFullYear() - i;
                  return (
                    <option key={year} value={year.toString()}>
                      {year}
                    </option>
                  );
                })}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400 pointer-events-none" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-600 mb-1.5">Tháng</label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <select
                value={filterMonth}
                onChange={(e) => setFilterMonth(e.target.value)}
                className="w-full pl-9 pr-9 py-2 border border-neutral-200 rounded-lg text-sm appearance-none bg-white"
              >
                <option value="all">Tất cả các tháng</option>
                {Array.from({ length: 12 }, (_, i) => {
                  const month = String(i + 1).padStart(2, '0');
                  return (
                    <option key={month} value={month}>
                      Tháng {i + 1}
                    </option>
                  );
                })}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400 pointer-events-none" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-neutral-600 mb-1.5">
              Tỉnh/Thành phố
            </label>
            <div className="relative">
              <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <select
                value={filterProvince}
                onChange={(e) => setFilterProvince(e.target.value)}
                className="w-full pl-9 pr-9 py-2 border border-neutral-200 rounded-lg text-sm appearance-none bg-white"
              >
                <option value="all">Tất cả tỉnh/thành</option>
                {provinces.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400 pointer-events-none" />
            </div>
          </div>
          <button
            onClick={() => {
              loadData();
              loadTrend();
            }}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            <Search className="w-4 h-4" /> Lọc
          </button>
        </div>
      </div>

      {/* Trend chart */}
      <div className="bg-white rounded-2xl border border-neutral-200 p-5">
        <h3 className="font-semibold text-neutral-900 mb-3">
          Xu hướng thay đổi các yếu tố thời tiết ({formatMonthLabel()})
        </h3>
        {trend.length === 0 ? (
          <div className="h-72 flex items-center justify-center text-sm text-neutral-400">
            Chưa có dữ liệu xu hướng. Hãy thêm hoặc import dữ liệu.
          </div>
        ) : (
          /* Small multiples: mỗi đại lượng một trục riêng — không dùng trục kép */
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { key: 'temp', name: 'Nhiệt độ', unit: '°C', color: SERIES.s6 },
              { key: 'humidity', name: 'Độ ẩm', unit: '%', color: SERIES.s1 },
              { key: 'rainfall', name: 'Lượng mưa', unit: 'mm', color: SERIES.s5 },
              { key: 'aqi', name: 'Chất lượng không khí (AQI)', unit: '', color: SERIES.s4 },
            ].map((m) => (
              <div key={m.key} className="rounded-xl border border-neutral-100 bg-neutral-50/40 p-3">
                <div className="flex items-center gap-2 mb-1 px-1">
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: m.color }} />
                  <p className="text-xs font-semibold text-neutral-600">
                    {m.name}
                    {m.unit ? <span className="text-neutral-400 font-normal"> ({m.unit})</span> : null}
                  </p>
                </div>
                <div className="h-36">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trend} margin={{ top: 6, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid {...gridProps} />
                      <XAxis
                        dataKey="year"
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: INK.axis, fontSize: 10 }}
                      />
                      <YAxis
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: INK.axis, fontSize: 10 }}
                        width={38}
                        domain={['auto', 'auto']}
                      />
                      <Tooltip
                        {...tooltipStyle}
                        formatter={(value: any) => [
                          `${Number(value).toLocaleString('vi-VN')}${m.unit ? ' ' + m.unit : ''}`,
                          m.name,
                        ]}
                      />
                      <Line
                        type="monotone"
                        dataKey={m.key}
                        name={m.name}
                        stroke={m.color}
                        strokeWidth={2}
                        dot={{ r: 2.5, strokeWidth: 1.5, stroke: '#ffffff', fill: m.color }}
                        activeDot={{ r: 4.5 }}
                        connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Data table */}
      <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
        {loading ? (
          <div className="h-64 flex items-center justify-center">
            <LoadingSpinner />
          </div>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-neutral-500 text-xs uppercase tracking-wide">
                  <th className="text-left px-6 py-3 font-medium">Tháng/Năm</th>
                  <th className="text-left px-6 py-3 font-medium">Khu vực</th>
                  <th className="text-right px-6 py-3 font-medium">Nhiệt độ (°C)</th>
                  <th className="text-right px-6 py-3 font-medium">Độ ẩm (%)</th>
                  <th className="text-right px-6 py-3 font-medium">Lượng mưa (mm)</th>
                  <th className="text-right px-6 py-3 font-medium">AQI</th>
                  <th className="text-right px-6 py-3 font-medium">PM2.5</th>
                  <th className="text-right px-6 py-3 font-medium">Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {paged.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-6 py-12 text-center text-neutral-400"
                    >
                      Không có dữ liệu
                    </td>
                  </tr>
                ) : (
                  paged.map((row) => (
                    <tr
                      key={row.id}
                      className="border-t border-neutral-100 hover:bg-neutral-50"
                    >
                      <td className="px-6 py-3 text-neutral-700">
                        {formatMonth(row.recorded_at)}
                      </td>
                      <td className="px-6 py-3 text-neutral-700">
                        {row.district_ward || row.location}
                      </td>
                      <td className="px-6 py-3 text-right text-neutral-700">
                        {fmt(row.temperature, 1)}
                      </td>
                      <td className="px-6 py-3 text-right text-neutral-700">
                        {fmt(row.humidity, 0)}
                      </td>
                      <td className="px-6 py-3 text-right text-neutral-700">
                        {fmt(row.rainfall, 1)}
                      </td>
                      <td className={`px-6 py-3 text-right ${aqiColor(row.air_quality_index)}`}>
                        {fmt(row.air_quality_index, 0)}
                      </td>
                      <td className={`px-6 py-3 text-right ${pm25Color(row.pm25)}`}>
                        {fmt(row.pm25, 1)}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <div className="inline-flex items-center gap-1">
                          <button
                            onClick={() => openEditForm(row)}
                            className="p-1.5 rounded hover:bg-blue-50 text-blue-600"
                            title="Chỉnh sửa"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => deleteRow(row.id)}
                            className="p-1.5 rounded hover:bg-red-50 text-red-500"
                            title="Xoá"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-3 border-t border-neutral-100 text-sm text-neutral-500">
              <span>
                Hiển thị {filtered.length === 0 ? 0 : startIdx + 1} đến{' '}
                {Math.min(startIdx + PAGE_SIZE, filtered.length)} trong số{' '}
                {filtered.length} kết quả
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={safePage <= 1}
                  className="p-1.5 border border-neutral-200 rounded-md disabled:opacity-30"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                {Array.from({ length: Math.min(totalPages, 5) }).map((_, idx) => {
                  const n = idx + 1;
                  return (
                    <button
                      key={n}
                      onClick={() => setPage(n)}
                      className={`w-8 h-8 rounded-md text-sm font-medium ${
                        safePage === n
                          ? 'bg-blue-600 text-white'
                          : 'border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
                      }`}
                    >
                      {n}
                    </button>
                  );
                })}
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={safePage >= totalPages}
                  className="p-1.5 border border-neutral-200 rounded-md disabled:opacity-30"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Form modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">
                {editing ? 'Chỉnh sửa dữ liệu thời tiết' : 'Thêm dữ liệu thời tiết mới'}
              </h3>
              <button
                onClick={() => setShowForm(false)}
                className="p-1 rounded hover:bg-neutral-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {formError}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <Field label="Tháng/Năm">
                <input
                  type="month"
                  value={form.month}
                  onChange={(e) => setForm({ ...form, month: e.target.value })}
                  className="input"
                />
              </Field>
              <Field label="Tỉnh/Thành phố">
                <select
                  value={
                    provinces.includes(form.province) ? form.province : '__custom__'
                  }
                  onChange={(e) => {
                    if (e.target.value === '__custom__') {
                      setForm({ ...form, province: '', district: '' });
                    } else {
                      setForm({ ...form, province: e.target.value, district: '' });
                    }
                  }}
                  className="input"
                >
                  {provinces.length === 0 && (
                    <option value="" disabled>
                      Chưa có tỉnh/thành — vui lòng nhập tay
                    </option>
                  )}
                  {provinces.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                  <option value="__custom__">+ Nhập mới...</option>
                </select>
                {!provinces.includes(form.province) && (
                  <input
                    type="text"
                    value={form.province}
                    onChange={(e) => setForm({ ...form, province: e.target.value })}
                    className="input mt-2"
                    placeholder="VD: TP. Hồ Chí Minh"
                  />
                )}
              </Field>
              <Field label="Phường/Xã">
                {(() => {
                  const list = getDistrictsForRegion(form.province, provinceDistricts);
                  const isInList = form.district && list.includes(form.district);
                  const value = form.district
                    ? isInList
                      ? form.district
                      : '__custom__'
                    : '';
                  return (
                    <>
                      <select
                        value={value}
                        onChange={(e) => {
                          if (e.target.value === '__custom__') {
                            setForm({ ...form, district: '' });
                          } else {
                            setForm({ ...form, district: e.target.value });
                          }
                        }}
                        className="input"
                      >
                        <option value="">— Không xác định —</option>
                        {list.map((d) => (
                          <option key={d} value={d}>
                            {d}
                          </option>
                        ))}
                        <option value="__custom__">+ Nhập mới...</option>
                      </select>
                      {value === '__custom__' && (
                        <input
                          type="text"
                          value={form.district}
                          onChange={(e) => setForm({ ...form, district: e.target.value })}
                          className="input mt-2"
                          placeholder="VD: Quận 1, Thành phố Thủ Đức"
                        />
                      )}
                    </>
                  );
                })()}
              </Field>
              <Field label="Nhiệt độ TB (°C)" hint="10–45°C">
                <input
                  type="number"
                  step="0.1"
                  value={form.temp}
                  onChange={(e) => setForm({ ...form, temp: Number(e.target.value) })}
                  className="input"
                />
              </Field>
              <Field label="Độ ẩm (%)" hint="0–100%">
                <input
                  type="number"
                  step="0.1"
                  value={form.humidity}
                  onChange={(e) => setForm({ ...form, humidity: Number(e.target.value) })}
                  className="input"
                />
              </Field>
              <Field label="Lượng mưa (mm)" hint="≥ 0">
                <input
                  type="number"
                  step="0.1"
                  value={form.rainfall}
                  onChange={(e) => setForm({ ...form, rainfall: Number(e.target.value) })}
                  className="input"
                />
              </Field>
              <Field label="AQI" hint="≥ 0">
                <input
                  type="number"
                  value={form.aqi}
                  onChange={(e) => setForm({ ...form, aqi: Number(e.target.value) })}
                  className="input"
                />
              </Field>
              <Field label="PM2.5 (µg/m³)" hint="≥ 0">
                <input
                  type="number"
                  step="0.1"
                  value={form.pm25}
                  onChange={(e) => setForm({ ...form, pm25: Number(e.target.value) })}
                  className="input"
                />
              </Field>
            </div>

            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setShowForm(false)}
                className="px-4 py-2 border border-neutral-200 rounded-lg text-sm hover:bg-neutral-50"
              >
                Huỷ
              </button>
              <button
                onClick={submitForm}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
              >
                Lưu
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .input {
          width: 100%;
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          border: 1px solid #e5e7eb;
          border-radius: 0.5rem;
          outline: none;
        }
        .input:focus {
          border-color: #2563eb;
          box-shadow: 0 0 0 2px rgba(37,99,235,0.1);
        }
      `}</style>

      {/* Import result modal */}
      {importResult && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-2xl shadow-xl max-h-[80vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Kết quả import</h3>
              <button
                onClick={() => setImportResult(null)}
                className="p-1 rounded hover:bg-neutral-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3">
                <p className="text-[11px] uppercase font-semibold text-emerald-700">Thêm mới</p>
                <p className="text-2xl font-extrabold text-emerald-700 mt-1 tabular-nums">
                  {importResult.imported.toLocaleString('vi-VN')}
                </p>
              </div>
              <div className="rounded-xl border border-blue-100 bg-blue-50 p-3">
                <p className="text-[11px] uppercase font-semibold text-blue-700">Cập nhật</p>
                <p className="text-2xl font-extrabold text-blue-700 mt-1 tabular-nums">
                  {importResult.updated.toLocaleString('vi-VN')}
                </p>
              </div>
              <div className="rounded-xl border border-amber-100 bg-amber-50 p-3">
                <p className="text-[11px] uppercase font-semibold text-amber-700">Bỏ qua</p>
                <p className="text-2xl font-extrabold text-amber-700 mt-1 tabular-nums">
                  {importResult.skipped.toLocaleString('vi-VN')}
                </p>
              </div>
            </div>
            {importResult.errors.length > 0 ? (
              <div className="flex-1 overflow-hidden flex flex-col">
                <p className="text-sm font-medium text-neutral-700 mb-2">
                  Các dòng cần sửa ({importResult.errors.length}
                  {importResult.truncated && '+'} dòng):
                </p>
                <div className="overflow-y-auto rounded-lg border border-neutral-200">
                  <table className="w-full text-sm">
                    <thead className="bg-neutral-50 sticky top-0">
                      <tr className="text-neutral-500 text-xs">
                        <th className="text-left px-3 py-2 font-medium">Dòng</th>
                        <th className="text-left px-3 py-2 font-medium">Lý do</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importResult.errors.map((e, idx) => (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2 text-neutral-700 font-medium">{e.row}</td>
                          <td className="px-3 py-2 text-neutral-600">{e.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {importResult.truncated && (
                  <p className="text-xs text-neutral-500 mt-2">
                    * Chỉ hiển thị 200 dòng lỗi đầu tiên — vui lòng kiểm tra file gốc.
                  </p>
                )}
              </div>
            ) : (
              <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
                ✓ Tất cả các dòng đã được xử lý thành công.
              </div>
            )}
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setImportResult(null)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-neutral-600 mb-1">
        {label}
        {hint && <span className="text-xs text-neutral-400 ml-1.5">({hint})</span>}
      </label>
      {children}
    </div>
  );
}

function fmt(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '—';
  return Number(v).toLocaleString('vi-VN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatMonth(iso: string): string {
  const d = new Date(iso);
  const m = String(d.getMonth() + 1).padStart(2, '0');
  return `${m}/${d.getFullYear()}`;
}
