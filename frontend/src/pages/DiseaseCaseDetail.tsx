import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Search,
  Eye,
  Pill,
  Activity,
  TrendingUp,
  TrendingDown,
  Loader2,
} from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import api from '../services/api';
import { DISEASE_TYPE_LABELS, type DiseaseType } from '../types/epidemiology';

interface SupplyItem {
  supply_id: number;
  code: string;
  name: string;
  category: string;
  unit: string;
  description?: string | null;
  ratio: number;
  used_quantity: number;
  disease_label: string;
  source?: 'actual' | 'estimated';
}

interface CaseDetailResponse {
  case: {
    id: number;
    recorded_at: string;
    month: number;
    year: number;
    disease_type: string;
    location: string;
    district_ward?: string | null;
    case_count: number;
    note?: string | null;
  };
  summary: {
    total_supply_types: number;
    total_cases: number;
    prev_total_cases: number;
    delta_cases_pct: number | null;
    prev_total_supply_types: number;
  };
  supplies: SupplyItem[];
}

export default function DiseaseCaseDetail() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { setPageTitle } = useUIStore();

  const [data, setData] = useState<CaseDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string>('');

  // Filters trong trang chi tiết
  const [supplyKeyword, setSupplyKeyword] = useState('');
  const [diseaseFilter, setDiseaseFilter] = useState<string>('all');
  
  // Phân trang
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  useEffect(() => {
    setPageTitle('Chi Tiết Sử Dụng Thuốc');
    if (!caseId) return;
    setLoading(true);
    api
      .get(`/disease-cases/${caseId}/supply-usage`)
      .then((res) => {
        setData(res.data);
        setErr('');
      })
      .catch((e: any) => {
        const msg =
          e?.response?.data?.detail || e?.message || 'Không thể tải chi tiết.';
        setErr(typeof msg === 'string' ? msg : 'Lỗi không xác định.');
      })
      .finally(() => setLoading(false));
  }, [caseId, setPageTitle]);

  const diseaseLabel = (k: string) => DISEASE_TYPE_LABELS[k as DiseaseType] || k;

  const filteredSupplies = useMemo(() => {
    if (!data) return [];
    return data.supplies.filter((s) => {
      if (
        diseaseFilter !== 'all' &&
        s.disease_label !== diseaseFilter &&
        diseaseLabel(s.disease_label) !== diseaseFilter
      ) {
        return false;
      }
      if (supplyKeyword.trim()) {
        const kw = supplyKeyword.trim().toLowerCase();
        return (
          s.name.toLowerCase().includes(kw) ||
          s.code.toLowerCase().includes(kw) ||
          (s.description ?? '').toLowerCase().includes(kw)
        );
      }
      return true;
    });
  }, [data, diseaseFilter, supplyKeyword]);

  // Reset trang về 1 khi filter thay đổi
  useEffect(() => {
    setCurrentPage(1);
  }, [diseaseFilter, supplyKeyword]);

  // Phân trang
  const totalPages = Math.ceil(filteredSupplies.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedSupplies = filteredSupplies.slice(startIndex, endIndex);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
      </div>
    );
  }

  if (err || !data) {
    return (
      <div className="bg-white rounded-2xl border border-red-100 p-6 text-center">
        <p className="text-red-600 font-medium">{err || 'Không có dữ liệu'}</p>
        <button
          onClick={() => navigate(-1)}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          Quay lại
        </button>
      </div>
    );
  }

  const monthLabel = `Tháng ${String(data.case.month).padStart(2, '0')}/${data.case.year}`;
  const regionLabel = data.case.district_ward
    ? `${data.case.district_ward}, ${data.case.location}`
    : data.case.location;
  const delta = data.summary.delta_cases_pct;

  const onExport = () => {
    // Tận dụng endpoint reports/export — mở luôn báo cáo dịch bệnh tháng hiện tại
    const params = new URLSearchParams({
      report_type: 'epidemic',
      format: 'pdf',
      from_month: `${data.case.year}-${String(data.case.month).padStart(2, '0')}`,
      to_month: `${data.case.year}-${String(data.case.month).padStart(2, '0')}`,
      disease_type: data.case.disease_type,
    });
    if (data.case.district_ward) params.append('region', data.case.district_ward);
    else params.append('region', data.case.location);
    window.open(
      `${api.defaults.baseURL}/reports/export?${params.toString()}`,
      '_blank',
    );
  };

  return (
    <div className="space-y-5">
      {/* Breadcrumb */}
      <div className="text-sm text-neutral-500">
        <button
          onClick={() => navigate('/epidemiology')}
          className="hover:text-blue-600"
        >
          Quản lý dữ liệu bệnh
        </button>
        <span className="mx-2 text-neutral-300">›</span>
        <span className="text-neutral-700">Chi tiết sử dụng thuốc</span>
      </div>

      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-3xl font-extrabold text-neutral-900">
              Chi Tiết Sử Dụng Thuốc
            </h2>
            <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-700">
              {monthLabel}
            </span>
          </div>
          <p className="text-sm text-neutral-500 mt-1 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5" />
            Khu vực: {regionLabel} · Bệnh: {diseaseLabel(data.case.disease_type)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/epidemiology')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            <ArrowLeft className="w-4 h-4" /> Quay lại danh sách
          </button>
          <button
            onClick={onExport}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700"
          >
            <Download className="w-4 h-4" /> Xuất báo cáo
          </button>
        </div>
      </div>

      {/* KPI cards + bộ lọc nhanh */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Tổng loại thuốc */}
        <div className="bg-gradient-to-br from-blue-50 to-white rounded-2xl border border-blue-100 p-5">
          <p className="text-xs font-semibold uppercase text-blue-700 tracking-wide">
            Tổng loại thuốc
          </p>
          <p className="text-4xl font-extrabold text-neutral-900 mt-2 tabular-nums">
            {data.summary.total_supply_types}
          </p>
          {data.summary.prev_total_supply_types > 0 && (
            <p
              className={`text-xs mt-1 inline-flex items-center gap-1 ${
                data.summary.total_supply_types >= data.summary.prev_total_supply_types
                  ? 'text-emerald-600'
                  : 'text-red-500'
              }`}
            >
              {data.summary.total_supply_types >= data.summary.prev_total_supply_types ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              {data.summary.total_supply_types - data.summary.prev_total_supply_types >= 0
                ? '+'
                : ''}
              {data.summary.total_supply_types - data.summary.prev_total_supply_types} loại
              so với tháng trước
            </p>
          )}
        </div>

        {/* Tổng số ca bệnh */}
        <div className="bg-gradient-to-br from-emerald-50 to-white rounded-2xl border border-emerald-100 p-5">
          <p className="text-xs font-semibold uppercase text-emerald-700 tracking-wide">
            Tổng số ca bệnh
          </p>
          <p className="text-4xl font-extrabold text-neutral-900 mt-2 tabular-nums">
            {data.summary.total_cases.toLocaleString('vi-VN')}
          </p>
          {delta !== null && (
            <p
              className={`text-xs mt-1 inline-flex items-center gap-1 ${
                delta >= 0 ? 'text-red-500' : 'text-emerald-600'
              }`}
            >
              {delta >= 0 ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              {delta >= 0 ? '+' : ''}
              {delta}% so với tháng trước
            </p>
          )}
        </div>

        {/* Bộ lọc nhanh */}
        <div className="bg-white rounded-2xl border border-neutral-200 p-5">
          <p className="text-xs font-semibold uppercase text-neutral-500 tracking-wide mb-3">
            Bộ lọc nhanh dữ liệu
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-neutral-500 mb-1">Loại bệnh</label>
              <select
                value={diseaseFilter}
                onChange={(e) => setDiseaseFilter(e.target.value)}
                className="w-full h-9 px-2 text-sm border border-neutral-200 rounded-lg bg-white"
              >
                <option value="all">Tất cả</option>
                <option value={data.case.disease_type}>
                  {diseaseLabel(data.case.disease_type)}
                </option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-neutral-500 mb-1">Tên thuốc</label>
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-400" />
                <input
                  value={supplyKeyword}
                  onChange={(e) => setSupplyKeyword(e.target.value)}
                  placeholder="Tìm theo tên thuốc..."
                  className="w-full h-9 pl-7 pr-2 text-sm border border-neutral-200 rounded-lg"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bảng danh sách thuốc đã cấp phát */}
      <div className="bg-white rounded-2xl border border-neutral-200">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-100">
          <div className="flex items-center gap-2">
            <Pill className="w-4 h-4 text-blue-600" />
            <h3 className="font-semibold text-neutral-800">
              Danh sách thuốc đã cấp phát
            </h3>
          </div>
          <p className="text-sm text-neutral-500">
            Hiển thị {filteredSupplies.length} / {data.supplies.length} kết quả
          </p>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-neutral-50">
            <tr className="text-neutral-500 text-xs uppercase tracking-wide">
              <th className="text-left px-6 py-3 font-medium">Mã thuốc</th>
              <th className="text-left px-6 py-3 font-medium">Tên thuốc</th>
              <th className="text-left px-6 py-3 font-medium">Đơn vị</th>
              <th className="text-right px-6 py-3 font-medium">Số lượng đã dùng</th>
              <th className="text-left px-6 py-3 font-medium">Đối tượng bệnh</th>
              <th className="text-right px-6 py-3 font-medium w-20">Hành động</th>
            </tr>
          </thead>
          <tbody>
            {paginatedSupplies.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-6 py-12 text-center text-neutral-400"
                >
                  {data.supplies.length === 0
                    ? 'Chưa có định mức vật tư cho bệnh này. Vào Module Quản trị → Định mức để thêm.'
                    : 'Không có thuốc nào khớp bộ lọc.'}
                </td>
              </tr>
            ) : (
              paginatedSupplies.map((s) => (
                <tr
                  key={s.supply_id}
                  className="border-t border-neutral-100 hover:bg-neutral-50"
                >
                  <td className="px-6 py-3">
                    <span className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 text-[11px] font-bold">
                      {s.code}
                    </span>
                  </td>
                  <td className="px-6 py-3">
                    <p className="font-semibold text-neutral-800">{s.name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {s.description && (
                        <p className="text-xs text-neutral-500 line-clamp-1">
                          {s.description}
                        </p>
                      )}
                      {s.source === 'estimated' && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 font-medium">
                          quy đổi
                        </span>
                      )}
                      {s.source === 'actual' && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-medium">
                          số liệu thực
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-3 text-neutral-600">{s.unit}</td>
                  <td className="px-6 py-3 text-right font-bold text-neutral-800 tabular-nums">
                    {s.used_quantity.toLocaleString('vi-VN')}
                  </td>
                  <td className="px-6 py-3">
                    <span className="px-2.5 py-1 rounded-full bg-cyan-50 text-cyan-700 text-xs font-medium">
                      {diseaseLabel(s.disease_label)}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right">
                    <button
                      onClick={() => navigate('/inventory')}
                      title="Xem trong tồn kho"
                      className="p-1.5 rounded hover:bg-blue-50 text-blue-600"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Footer với phân trang */}
        {filteredSupplies.length > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 border-t border-neutral-100 text-sm text-neutral-500">
            <span className="text-xs">
              Hiển thị {startIndex + 1}-{Math.min(endIndex, filteredSupplies.length)} trong số {filteredSupplies.length} kết quả
            </span>
            
            {totalPages > 1 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 text-xs border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Trước
                </button>
                
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    // Hiển thị tối đa 5 trang
                    let pageNum;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }
                    
                    return (
                      <button
                        key={pageNum}
                        onClick={() => setCurrentPage(pageNum)}
                        className={`w-8 h-8 text-xs rounded-lg ${
                          currentPage === pageNum
                            ? 'bg-blue-600 text-white font-medium'
                            : 'border border-neutral-200 text-neutral-600 hover:bg-neutral-50'
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>
                
                <button
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 text-xs border border-neutral-200 rounded-lg hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Sau
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
