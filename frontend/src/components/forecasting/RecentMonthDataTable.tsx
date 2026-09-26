import { useState, useEffect } from 'react';
import { Filter, Loader2 } from 'lucide-react';
import api from '../../services/api';

interface DiseaseCaseData {
  month: string; // 'MM/YYYY'
  disease_name: string;
  /** Khoá ghép nội bộ (mã ICD hoặc mã nhóm) để nối ca thực tế với dự báo. */
  matchKey: string;
  total_cases: number;
  predicted_cases?: number;
  deviation_pct?: number;
  location: string;
}

// Ba nhóm ICD của đề tài, phải khớp backend (app/utils/icd_groups.py, NHOM_ICD);
// ca thực tế gộp lên cấp nhóm rồi ghép với dự báo theo mã, không so tên bệnh.
const NHOM_ICD: Record<string, string> = {
  'J00-J06': 'Nhiễm khuẩn cấp đường hô hấp trên',
  'J09-J18': 'Cúm và viêm phổi',
  'J20-J22': 'Nhiễm khuẩn cấp đường hô hấp dưới khác',
};

/** 'J09-J18' → ['J09', 'J10', ..., 'J18']. */
const maThuocNhom = (nhom: string): string[] => {
  const [dau, cuoi] = nhom.split('-');
  if (!dau || !cuoi) return [];
  const chu = dau[0];
  const start = parseInt(dau.slice(1), 10);
  const end = parseInt(cuoi.slice(1), 10);
  if (Number.isNaN(start) || Number.isNaN(end)) return [];
  const out: string[] = [];
  for (let n = start; n <= end; n++) out.push(`${chu}${String(n).padStart(2, '0')}`);
  return out;
};

/** 'J13' → 'J09-J18'; undefined nếu mã ngoài 3 nhóm đề tài. */
const nhomCuaMa = (icdCode?: string | null): string | undefined => {
  const ma = (icdCode || '').trim().toUpperCase().slice(0, 3);
  if (!ma) return undefined;
  return Object.keys(NHOM_ICD).find((nhom) => maThuocNhom(nhom).includes(ma));
};

/** Khoá nhóm của một ca: ưu tiên disease_group, rồi suy từ icd_code, cuối cùng giữ mã lẻ. */
const resolveGroup = (
  icdCode?: string | null,
  diseaseGroup?: string | null
): string | undefined => {
  if (diseaseGroup && diseaseGroup in NHOM_ICD) return diseaseGroup;
  return nhomCuaMa(icdCode);
};

interface Props {
  currentMonth?: number;
  currentYear?: number;
  /** Bệnh vừa phân tích, để lọc sẵn bảng; parent remount qua key={forecast.id}
   *  nên chỉ cần đặt state khởi tạo, không cần effect đồng bộ. */
  diseaseLabel?: string;
  /** Tỉnh/thành vừa phân tích ('all' = Toàn quốc), để lọc sẵn bảng. */
  regionFilter?: string;
}

// Chuẩn hoá tên tỉnh/thành để gộp biến thể
const normalizeLocation = (location: string): string => {
  const normalized = location.trim();
  
  const hcmVariants = [
    'tp hồ chí minh',
    'tp. hồ chí minh',
    'thành phố hồ chí minh',
    'hồ chí minh',
    'tp hcm',
    'tphcm',
    'hcm',
    'sài gòn',
    'saigon',
  ];
  
  if (hcmVariants.includes(normalized.toLowerCase())) {
    return 'Thành phố Hồ Chí Minh';
  }
  
  const hnVariants = ['hà nội', 'ha noi', 'hanoi'];
  if (hnVariants.includes(normalized.toLowerCase())) {
    return 'Hà Nội';
  }
  
  return normalized;
};

export default function RecentMonthDataTable({ currentMonth, currentYear, diseaseLabel, regionFilter }: Props) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DiseaseCaseData[]>([]);
  // Temp = đang chỉnh trên dropdown; Applied = đã bấm Lọc. Mặc định lọc theo bệnh/khu vực vừa phân tích.
  const initialDisease = diseaseLabel || 'all';
  const initialLocation =
    regionFilter && regionFilter !== 'all' ? normalizeLocation(regionFilter) : 'all';
  const [tempMonth, setTempMonth] = useState<string>('latest');
  const [tempDisease, setTempDisease] = useState<string>(initialDisease);
  const [tempLocation, setTempLocation] = useState<string>(initialLocation);
  const [filterMonth, setFilterMonth] = useState<string>('latest');
  const [filterDisease, setFilterDisease] = useState<string>(initialDisease);
  const [filterLocation, setFilterLocation] = useState<string>(initialLocation);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Tháng liền trước tháng dự báo
  const latestMonth = currentMonth && currentYear 
    ? (() => {
        const m = currentMonth - 1;
        const y = m <= 0 ? currentYear - 1 : currentYear;
        const finalM = m <= 0 ? 12 + m : m;
        return `${String(finalM).padStart(2, '0')}/${y}`;
      })()
    : null;

  useEffect(() => {
    loadData();
  }, [currentMonth, currentYear]);

  const loadData = async () => {
    try {
      setLoading(true);
      // limit cao để không mất khu vực khi ghép forecast
      const [casesResponse, forecastResponse] = await Promise.all([
        api.get('/disease-cases/', {
          params: { limit: 50000 },
        }),
        api.get('/forecast/history', {
          params: { limit: 1000 },
        }).catch(() => ({ data: [] })), // chưa có forecast
      ]);
      
      // Gộp ca theo tháng + nhóm ICD + khu vực, cùng cấp với dự báo. Một lượt khám
      // 2 chẩn đoán cùng nhóm có thể đếm 2 lần, nên bảng chỉ để đối chiếu nhanh.
      const grouped: Record<string, DiseaseCaseData> = {};

      casesResponse.data.forEach((item: any) => {
        const date = new Date(item.recorded_at);
        const month = `${String(date.getMonth() + 1).padStart(2, '0')}/${date.getFullYear()}`;
        const normalizedLocation = normalizeLocation(item.location || 'Toàn quốc');
        const groupCode = resolveGroup(item.icd_code, item.disease_group);
        const matchKey = groupCode || item.icd_code || item.disease_name;
        const displayName = groupCode ? NHOM_ICD[groupCode] : item.disease_name;
        const key = `${month}_${matchKey}_${normalizedLocation}`;

        if (!grouped[key]) {
          grouped[key] = {
            month,
            disease_name: displayName,
            matchKey,
            total_cases: 0,
            location: normalizedLocation,
          };
        }
        grouped[key].total_cases += item.case_count || 0;
      });

      // Ghép dự báo bằng icd_code (mã nhóm hoặc mã lẻ, đều khớp matchKey), không so tên.
      forecastResponse.data.forEach((forecast: any) => {
        const month = forecast.month; // MM/YYYY
        const matchKey: string = forecast.icd_code || forecast.disease_label || forecast.disease_name;
        const displayName = NHOM_ICD[matchKey] || forecast.disease_label || forecast.disease_name;
        const normalizedLocation = normalizeLocation(forecast.region || 'Toàn thành phố');
        const key = `${month}_${matchKey}_${normalizedLocation}`;

        if (grouped[key]) {
          grouped[key].predicted_cases = forecast.predicted_cases;
          if (forecast.actual_cases != null) {
            grouped[key].total_cases = forecast.actual_cases;
          }
          if (forecast.deviation_pct != null) {
            grouped[key].deviation_pct = forecast.deviation_pct;
          } else if (grouped[key].total_cases > 0) {
            grouped[key].deviation_pct =
              ((forecast.predicted_cases - grouped[key].total_cases) / grouped[key].total_cases) * 100;
          }
        } else {
          // Bản Toàn quốc không khớp dòng thực tế nào (disease_cases luôn có tỉnh);
          // số thực tế lấy bằng tổng các tỉnh cùng tháng + nhóm bệnh để khớp nguồn.
          let actual = forecast.actual_cases;
          if (actual == null && forecast.is_nationwide) {
            const tienTo = `${month}_${matchKey}_`;
            actual = Object.entries(grouped)
              .filter(([k, v]) => k.startsWith(tienTo) && v.location !== 'Toàn quốc')
              .reduce((tong, [, v]) => tong + (v.total_cases || 0), 0);
          }
          const tongThucTe = actual || 0;
          grouped[key] = {
            month,
            disease_name: displayName,
            matchKey,
            total_cases: tongThucTe,
            predicted_cases: forecast.predicted_cases,
            deviation_pct:
              forecast.deviation_pct ??
              (tongThucTe > 0
                ? ((forecast.predicted_cases - tongThucTe) / tongThucTe) * 100
                : undefined),
            location: normalizedLocation,
          };
        }
      });

      const result = Object.values(grouped).sort((a, b) => {
        const [aM, aY] = a.month.split('/').map(Number);
        const [bM, bY] = b.month.split('/').map(Number);
        if (aY !== bY) return bY - aY;
        return bM - aM;
      });

      setData(result);
    } catch (err) {
      console.error('Failed to load disease case data:', err);
    } finally {
      setLoading(false);
    }
  };

  const uniqueMonths = Array.from(new Set(data.map((d) => d.month))).sort((a, b) => {
    const [aM, aY] = a.split('/').map(Number);
    const [bM, bY] = b.split('/').map(Number);
    if (aY !== bY) return bY - aY;
    return bM - aM;
  });

  const uniqueDiseases = Array.from(new Set(data.map((d) => d.disease_name))).sort();
  
  const uniqueLocations = Array.from(new Set(data.map((d) => d.location))).sort();

  // So sánh sau trim để tránh lệch do khoảng trắng
  const filteredData = data.filter((item) => {
    if (filterMonth === 'latest') {
      if (item.month !== latestMonth) return false;
    } else if (filterMonth !== 'all' && item.month !== filterMonth) {
      return false;
    }
    if (
      filterDisease !== 'all' &&
      (item.disease_name ?? '').trim() !== filterDisease.trim()
    ) {
      return false;
    }
    if (
      filterLocation !== 'all' &&
      (item.location ?? '').trim() !== filterLocation.trim()
    ) {
      return false;
    }
    return true;
  });

  useEffect(() => {
    setCurrentPage(1);
  }, [filterMonth, filterDisease, filterLocation]);

  const totalPages = Math.ceil(filteredData.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedData = filteredData.slice(startIndex, endIndex);

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">
            Dữ liệu ca bệnh gần đây
          </h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            {filterMonth === 'latest' && latestMonth
              ? `Tháng ${latestMonth} (tháng gần nhất)`
              : 'Dữ liệu đã nhập vào hệ thống'}
          </p>
        </div>
      </div>

      {/* Bộ lọc */}
      <div className="px-5 py-3 bg-neutral-50 border-y border-neutral-100">
        <div className="flex flex-wrap items-end gap-x-3 gap-y-3">
          <label className="block w-48">
            <span className="block text-xs font-medium text-neutral-600 mb-1">Tháng</span>
            <select
              value={tempMonth}
              onChange={(e) => setTempMonth(e.target.value)}
              className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            >
              <option value="latest">Tháng gần nhất ({latestMonth || '—'})</option>
              <option value="all">Tất cả các tháng</option>
              {uniqueMonths.map((m) => (
                <option key={m} value={m}>
                  Tháng {m}
                </option>
              ))}
            </select>
          </label>

          <label className="block flex-1 min-w-[240px] max-w-sm">
            <span className="block text-xs font-medium text-neutral-600 mb-1">Bệnh</span>
            <select
              value={tempDisease}
              onChange={(e) => setTempDisease(e.target.value)}
              className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            >
              <option value="all">Tất cả bệnh</option>
              {uniqueDiseases.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </label>

          <label className="block w-52">
            <span className="block text-xs font-medium text-neutral-600 mb-1">Tỉnh/Thành</span>
            <select
              value={tempLocation}
              onChange={(e) => setTempLocation(e.target.value)}
              className="w-full h-9 px-3 rounded-lg border border-neutral-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            >
              <option value="all">Tất cả khu vực</option>
              {uniqueLocations.map((loc) => (
                <option key={loc} value={loc}>
                  {loc}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={() => {
              setFilterMonth(tempMonth);
              setFilterDisease(tempDisease);
              setFilterLocation(tempLocation);
            }}
            className="inline-flex items-center gap-1.5 h-9 px-4 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700"
          >
            <Filter className="w-3.5 h-3.5" />
            Lọc
          </button>
          {(tempMonth !== 'latest' ||
            tempDisease !== initialDisease ||
            tempLocation !== initialLocation ||
            filterMonth !== 'latest' ||
            filterDisease !== initialDisease ||
            filterLocation !== initialLocation) && (
            <button
              type="button"
              onClick={() => {
                setTempMonth('latest');
                setTempDisease(initialDisease);
                setTempLocation(initialLocation);
                setFilterMonth('latest');
                setFilterDisease(initialDisease);
                setFilterLocation(initialLocation);
              }}
              className="inline-flex items-center gap-1.5 h-9 px-3 border border-neutral-200 rounded-lg text-xs text-neutral-600 bg-white hover:bg-neutral-100"
            >
              Đặt lại bộ lọc
            </button>
          )}
        </div>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="text-neutral-500 text-xs border-y border-neutral-100">
            <th className="text-left px-5 py-3 font-medium">Tháng</th>
            <th className="text-left px-5 py-3 font-medium">Bệnh</th>
            <th className="text-left px-5 py-3 font-medium">Khu vực</th>
            <th className="text-right px-5 py-3 font-medium">Số ca dự báo</th>
            <th className="text-right px-5 py-3 font-medium">Số ca thực tế</th>
            <th
              className="text-right px-5 py-3 font-medium"
              title="Độ lệch = (Số ca dự báo − Số ca thực tế) / Số ca thực tế × 100%. Dương = dự báo cao hơn thực tế; âm = dự báo thấp hơn. Để trống khi số ca thực tế bằng 0."
            >
              <span className="underline decoration-dotted decoration-neutral-300 underline-offset-4 cursor-help">
                Độ lệch
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={6} className="py-8">
                <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Đang tải dữ liệu...
                </div>
              </td>
            </tr>
          ) : data.length === 0 ? (
            <tr>
              <td colSpan={6} className="py-10 text-center text-sm text-neutral-400">
                Chưa có dữ liệu ca bệnh
              </td>
            </tr>
          ) : filteredData.length === 0 ? (
            <tr>
              <td colSpan={6} className="py-10 text-center text-sm text-neutral-400">
                Không tìm thấy dữ liệu phù hợp với bộ lọc
              </td>
            </tr>
          ) : (
            paginatedData.map((item, idx) => (
              <tr key={idx} className="border-t border-neutral-100">
                <td className="px-5 py-3.5 text-neutral-700">Tháng {item.month}</td>
                <td className="px-5 py-3.5 text-neutral-700">{item.disease_name}</td>
                <td className="px-5 py-3.5 text-neutral-500 text-xs">{item.location}</td>
                <td className="px-5 py-3.5 text-right text-blue-600 font-semibold tabular-nums">
                  {item.predicted_cases != null ? item.predicted_cases.toLocaleString('vi-VN') : '—'}
                </td>
                <td className="px-5 py-3.5 text-right text-neutral-900 font-semibold tabular-nums">
                  {item.total_cases.toLocaleString('vi-VN')}
                </td>
                <td
                  className="px-5 py-3.5 text-right font-semibold tabular-nums"
                  title={
                    item.deviation_pct != null
                      ? `(${item.predicted_cases ?? 0} − ${item.total_cases}) / ${item.total_cases} × 100% = ${item.deviation_pct.toFixed(1)}%`
                      : 'Không tính được: số ca thực tế bằng 0'
                  }
                >
                  {item.deviation_pct != null ? (
                    <span className={
                      Math.abs(item.deviation_pct) <= 10 
                        ? 'text-emerald-600' 
                        : Math.abs(item.deviation_pct) <= 25
                        ? 'text-amber-600'
                        : 'text-red-600'
                    }>
                      {item.deviation_pct > 0 ? '+' : ''}{item.deviation_pct.toFixed(1)}%
                    </span>
                  ) : (
                    <span className="text-neutral-400">—</span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {!loading && filteredData.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-t border-neutral-100 text-sm text-neutral-500">
          <span className="text-xs">
            Hiển thị {startIndex + 1}-{Math.min(endIndex, filteredData.length)} trong số {filteredData.length} kết quả
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
                  // Tối đa 5 nút trang
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
  );
}
