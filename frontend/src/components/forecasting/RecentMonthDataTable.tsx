import { useState, useEffect } from 'react';
import { Filter, Loader2 } from 'lucide-react';
import api from '../../services/api';

interface DiseaseCaseData {
  month: string; // 'MM/YYYY'
  disease_name: string;
  /** Khoá ghép nội bộ (mã ICD hoặc mã NHÓM) — không hiển thị, chỉ dùng để
   *  nối ca bệnh thực tế với dự báo. Xem giải thích ở resolveGroup() bên dưới. */
  matchKey: string;
  total_cases: number;
  predicted_cases?: number;
  deviation_pct?: number;
  location: string;
}

// Ba nhóm ICD của đề tài — PHẢI khớp với backend (app/utils/icd_groups.py,
// NHOM_ICD). Từ 08/2026, trang Dự báo lưu disease_forecasts.icd_code ở CẤP
// NHÓM (vd 'J09-J18'), trong khi /disease-cases/ vẫn trả disease_name ở cấp
// MÃ lẻ (vd 'Viêm phổi, tác nhân không xác định'). Ghép hai bên bằng so
// chuỗi disease_name tự do (cách cũ) không bao giờ khớp vì khác cấp — đây là
// lý do cột "Số ca dự báo"/"Độ lệch" luôn trống. Sửa bằng cách ghép theo MÃ,
// gộp ca bệnh thực tế lên cùng cấp NHÓM với dự báo trước khi so sánh.
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

/** 'J13' → 'J09-J18'. undefined nếu mã không thuộc nhóm nào trong 3 nhóm đề tài. */
const nhomCuaMa = (icdCode?: string | null): string | undefined => {
  const ma = (icdCode || '').trim().toUpperCase().slice(0, 3);
  if (!ma) return undefined;
  return Object.keys(NHOM_ICD).find((nhom) => maThuocNhom(nhom).includes(ma));
};

/** Suy ra khoá NHÓM cho 1 ca bệnh: ưu tiên cột disease_group đã đồng bộ sẵn,
 *  rơi về suy từ icd_code nếu cột đó chưa có (bản ghi cũ), cuối cùng mới
 *  giữ nguyên mã lẻ cho bệnh ngoài 3 nhóm đề tài đang theo dõi. */
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
}

// Chuẩn hóa tên tỉnh/thành để gộp các biến thể khác nhau
const normalizeLocation = (location: string): string => {
  const normalized = location.trim();
  
  // Map các biến thể của TPHCM về 1 tên chuẩn
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
  
  // Các tỉnh khác có thể chuẩn hóa tương tự
  const hnVariants = ['hà nội', 'ha noi', 'hanoi'];
  if (hnVariants.includes(normalized.toLowerCase())) {
    return 'Hà Nội';
  }
  
  // Trả về tên gốc nếu không match
  return normalized;
};

export default function RecentMonthDataTable({ currentMonth, currentYear }: Props) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DiseaseCaseData[]>([]);
  // Thanh lọc cố định — luôn hiển thị, không còn ẩn/hiện qua nút bấm.
  // Temp = đang chỉnh trên dropdown; Applied = đã bấm Lọc, dùng để filter thật.
  const [tempMonth, setTempMonth] = useState<string>('latest');
  const [tempDisease, setTempDisease] = useState<string>('all');
  const [tempLocation, setTempLocation] = useState<string>('all');
  const [filterMonth, setFilterMonth] = useState<string>('latest');
  const [filterDisease, setFilterDisease] = useState<string>('all');
  const [filterLocation, setFilterLocation] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Tính tháng gần nhất (tháng trước tháng dự báo)
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
      // Lấy dữ liệu ca bệnh thực tế + dự báo từ backend.
      // Tăng limit cao để không bị cắt mất khu vực khi ghép forecast.
      const [casesResponse, forecastResponse] = await Promise.all([
        api.get('/disease-cases/', {
          params: { limit: 50000 },
        }),
        api.get('/forecast/history', {
          params: { limit: 1000 },
        }).catch(() => ({ data: [] })), // Fallback nếu chưa có dữ liệu forecast
      ]);
      
      // Group cases by month + (NHÓM ICD nếu có, mã lẻ nếu không) + location.
      // Gộp theo NHÓM vì dự báo (xem forEach forecast bên dưới) được lưu ở
      // cấp nhóm — phải cùng cấp mới ghép được. Lưu ý: nếu 1 lượt khám có 2
      // chẩn đoán trong cùng nhóm, tổng theo nhóm ở đây có thể đếm lượt đó 2
      // lần (đặc thù dữ liệu HIS đã ghi ở sql_his/README.md, không phải lỗi
      // riêng của bảng này) — chỉ dùng để đối chiếu nhanh, không thay số
      // chính thức từ tầng MART.
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

      // Thêm dữ liệu dự báo vào grouped data — ghép bằng MÃ (icd_code), không
      // so tên tiếng Việt tự do. forecast.icd_code là mã NHÓM ('J09-J18') cho
      // dự báo mới, hoặc mã lẻ cho dự báo cũ tương thích ngược — cả hai
      // trường hợp đều khớp đúng với matchKey đã tính ở trên.
      forecastResponse.data.forEach((forecast: any) => {
        const month = forecast.month; // Đã ở dạng MM/YYYY
        const matchKey: string = forecast.icd_code || forecast.disease_label || forecast.disease_name;
        const displayName = NHOM_ICD[matchKey] || forecast.disease_label || forecast.disease_name;
        const normalizedLocation = normalizeLocation(forecast.region || 'Toàn thành phố');
        const key = `${month}_${matchKey}_${normalizedLocation}`;

        if (grouped[key]) {
          // Đã có dữ liệu thực tế, thêm forecast và deviation
          grouped[key].predicted_cases = forecast.predicted_cases;
          if (forecast.actual_cases != null) {
            grouped[key].total_cases = forecast.actual_cases;
          }
          if (forecast.deviation_pct != null) {
            grouped[key].deviation_pct = forecast.deviation_pct;
          } else if (grouped[key].total_cases > 0) {
            // Tính deviation nếu chưa có
            grouped[key].deviation_pct =
              ((forecast.predicted_cases - grouped[key].total_cases) / grouped[key].total_cases) * 100;
          }
        } else {
          // Chỉ có dự báo, chưa có thực tế (vd chưa đến kỳ đóng dữ liệu tháng đó)
          grouped[key] = {
            month,
            disease_name: displayName,
            matchKey,
            total_cases: forecast.actual_cases || 0,
            predicted_cases: forecast.predicted_cases,
            deviation_pct: forecast.deviation_pct,
            location: normalizedLocation,
          };
        }
      });

      const result = Object.values(grouped).sort((a, b) => {
        // Sort by month descending
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

  // Lấy danh sách tháng, bệnh và khu vực unique từ dữ liệu thực tế
  const uniqueMonths = Array.from(new Set(data.map((d) => d.month))).sort((a, b) => {
    const [aM, aY] = a.split('/').map(Number);
    const [bM, bY] = b.split('/').map(Number);
    if (aY !== bY) return bY - aY;
    return bM - aM;
  });

  const uniqueDiseases = Array.from(new Set(data.map((d) => d.disease_name))).sort();
  
  const uniqueLocations = Array.from(new Set(data.map((d) => d.location))).sort();

  // Lọc data — so sánh đã chuẩn hoá (trim) để tránh lệch do khoảng trắng.
  const filteredData = data.filter((item) => {
    // 1. Tháng
    if (filterMonth === 'latest') {
      if (item.month !== latestMonth) return false;
    } else if (filterMonth !== 'all' && item.month !== filterMonth) {
      return false;
    }
    // 2. Bệnh
    if (
      filterDisease !== 'all' &&
      (item.disease_name ?? '').trim() !== filterDisease.trim()
    ) {
      return false;
    }
    // 3. Khu vực
    if (
      filterLocation !== 'all' &&
      (item.location ?? '').trim() !== filterLocation.trim()
    ) {
      return false;
    }
    return true;
  });

  // Reset trang về 1 khi filter thay đổi
  useEffect(() => {
    setCurrentPage(1);
  }, [filterMonth, filterDisease, filterLocation]);

  // Phân trang
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

      {/* Filter panel — cố định, luôn hiển thị */}
      <div className="px-5 py-3 bg-neutral-50 border-y border-neutral-100 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="block">
              <span className="text-xs font-medium text-neutral-600 mb-1.5 block">
                Tháng
              </span>
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

            <label className="block">
              <span className="text-xs font-medium text-neutral-600 mb-1.5 block">
                Bệnh
              </span>
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

            <label className="block">
              <span className="text-xs font-medium text-neutral-600 mb-1.5 block">
                Tỉnh/Thành
              </span>
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
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setFilterMonth(tempMonth);
                setFilterDisease(tempDisease);
                setFilterLocation(tempLocation);
              }}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700"
            >
              <Filter className="w-3.5 h-3.5" />
              Lọc
            </button>
            {(tempMonth !== 'latest' ||
              tempDisease !== 'all' ||
              tempLocation !== 'all' ||
              filterMonth !== 'latest' ||
              filterDisease !== 'all' ||
              filterLocation !== 'all') && (
              <button
                type="button"
                onClick={() => {
                  setTempMonth('latest');
                  setTempDisease('all');
                  setTempLocation('all');
                  setFilterMonth('latest');
                  setFilterDisease('all');
                  setFilterLocation('all');
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-neutral-200 rounded-lg text-xs text-neutral-600 hover:bg-white"
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
            <th className="text-right px-5 py-3 font-medium">Số ca thực tế</th>
            <th className="text-right px-5 py-3 font-medium">Số ca dự báo</th>
            <th className="text-right px-5 py-3 font-medium">Độ lệch</th>
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
                <td className="px-5 py-3.5 text-right text-neutral-900 font-semibold tabular-nums">
                  {item.total_cases.toLocaleString('vi-VN')}
                </td>
                <td className="px-5 py-3.5 text-right text-blue-600 font-semibold tabular-nums">
                  {item.predicted_cases != null ? item.predicted_cases.toLocaleString('vi-VN') : '—'}
                </td>
                <td className="px-5 py-3.5 text-right font-semibold tabular-nums">
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
  );
}
