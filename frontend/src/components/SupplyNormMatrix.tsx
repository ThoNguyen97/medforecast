/**
 * Hiển thị ma trận định mức thuốc/vật tư theo 3 cấp độ (nhẹ/trung bình/nặng)
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, AlertCircle, TrendingUp, Search } from 'lucide-react';
import { cn } from '../utils/cn';

type SeverityLevel = 'all' | 'mild' | 'moderate' | 'severe';

interface Supply {
  supply_id: number;
  supply_code: string;
  drug_code?: string;
  ten_hoat_chat: string;
  unit: string;
  group_name?: string;
  mild: number;
  moderate: number;
  severe: number;
}

interface SeverityRate {
  mild_rate: number;
  moderate_rate: number;
  severe_rate: number;
}

interface NormMatrix {
  icd_code: string;
  disease_name: string;
  severity_rate: SeverityRate;
  supplies: Supply[];
}

interface SupplyNormMatrixProps {
  selectedDisease?: string;
  onDiseaseChange?: (icd_code: string) => void;
  /** Bật bộ lọc tìm kiếm + lọc theo cấp độ (chỉ dùng ở trang /inventory) */
  showFilters?: boolean;
}

export const SupplyNormMatrix: React.FC<SupplyNormMatrixProps> = ({
  selectedDisease = 'J20',
  onDiseaseChange,
  showFilters = false,
}) => {
  const [matrix, setMatrix] = useState<NormMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disease, setDisease] = useState(selectedDisease);
  const [search, setSearch] = useState('');
  const [level, setLevel] = useState<SeverityLevel>('all');

  const diseases = [
    { label: 'J20 - Viêm phế quản cấp', value: 'J20' },
    { label: 'J06 - Viêm đường hô hấp cấp khác', value: 'J06' },
    { label: 'J02 - Viêm họng cấp', value: 'J02' },
    { label: 'J01 - Viêm xoang cấp', value: 'J01' },
  ];

  useEffect(() => {
    fetchNormMatrix(disease);
  }, [disease]);

  const fetchNormMatrix = async (icd_code: string) => {
    try {
      setLoading(true);
      setError(null);
      const token = localStorage.getItem('medforecast_token');
      const response = await fetch(
        `/api/v1/admin/supply-norms/matrix?icd_code=${icd_code}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Bạn chưa đăng nhập hoặc phiên hết hạn');
        }
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      setMatrix(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi không xác định');
    } finally {
      setLoading(false);
    }
  };

  const handleDiseaseChange = (value: string) => {
    setDisease(value);
    onDiseaseChange?.(value);
  };

  // Lọc danh sách thuốc theo từ khoá tìm kiếm + cấp độ
  const filteredSupplies = useMemo(() => {
    const list = matrix?.supplies ?? [];
    const q = search.trim().toLowerCase();
    return list.filter((s) => {
      // Lọc theo từ khoá (mã / tên hoạt chất / nhóm)
      if (q) {
        const haystack = `${s.supply_code} ${s.drug_code ?? ''} ${s.ten_hoat_chat} ${s.group_name ?? ''}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      // Lọc theo cấp độ: chỉ hiện thuốc có định mức > 0 ở cấp độ đang chọn
      if (level !== 'all' && (s[level] ?? 0) <= 0) return false;
      return true;
    });
  }, [matrix, search, level]);

  // Cấu hình hiển thị cột theo cấp độ đang chọn
  const showMild = level === 'all' || level === 'mild';
  const showModerate = level === 'all' || level === 'moderate';
  const showSevere = level === 'all' || level === 'severe';

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-neutral-200 p-12 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
          <p className="text-sm text-neutral-600">Đang tải dữ liệu...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-2xl border border-neutral-200 p-8">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
          <div>
            <h3 className="font-semibold text-red-900">Lỗi</h3>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!matrix) {
    return (
      <div className="bg-white rounded-2xl border border-neutral-200 p-8 text-center">
        <p className="text-neutral-600">Không có dữ liệu</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header Card */}
      <div className="bg-white rounded-2xl border border-neutral-200 p-6">
        <div className="space-y-4">
          {/* Disease Selector */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">
              Chọn bệnh:
            </label>
            <select
              value={disease}
              onChange={(e) => handleDiseaseChange(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            >
              {diseases.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>

          {/* Severity Rates */}
          <div className="grid grid-cols-3 gap-3">
            <button
              type="button"
              onClick={() => setLevel(level === 'mild' ? 'all' : 'mild')}
              className={cn(
                'text-left rounded-lg border bg-emerald-50 p-3 transition',
                level === 'mild'
                  ? 'border-emerald-500 ring-2 ring-emerald-500/30'
                  : 'border-emerald-100 hover:border-emerald-300'
              )}
            >
              <div className="text-xs font-semibold text-emerald-700 uppercase">Nhẹ (Mild)</div>
              <div className="text-2xl font-bold text-emerald-900 mt-1">
                {matrix.severity_rate.mild_rate.toFixed(1)}%
              </div>
            </button>
            <button
              type="button"
              onClick={() => setLevel(level === 'moderate' ? 'all' : 'moderate')}
              className={cn(
                'text-left rounded-lg border bg-amber-50 p-3 transition',
                level === 'moderate'
                  ? 'border-amber-500 ring-2 ring-amber-500/30'
                  : 'border-amber-100 hover:border-amber-300'
              )}
            >
              <div className="text-xs font-semibold text-amber-700 uppercase">Trung bình (Moderate)</div>
              <div className="text-2xl font-bold text-amber-900 mt-1">
                {matrix.severity_rate.moderate_rate.toFixed(1)}%
              </div>
            </button>
            <button
              type="button"
              onClick={() => setLevel(level === 'severe' ? 'all' : 'severe')}
              className={cn(
                'text-left rounded-lg border bg-red-50 p-3 transition',
                level === 'severe'
                  ? 'border-red-500 ring-2 ring-red-500/30'
                  : 'border-red-100 hover:border-red-300'
              )}
            >
              <div className="text-xs font-semibold text-red-700 uppercase">Nặng (Severe)</div>
              <div className="text-2xl font-bold text-red-900 mt-1">
                {matrix.severity_rate.severe_rate.toFixed(1)}%
              </div>
            </button>
          </div>

          {/* Filter: tìm kiếm + chọn cấp độ */}
          {showFilters && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Tìm theo mã, tên hoạt chất, nhóm..."
                className="w-full pl-9 pr-3 py-2.5 rounded-lg border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              />
            </div>
            <div className="inline-flex rounded-lg border border-neutral-300 overflow-hidden">
              {([
                { key: 'all', label: 'Tất cả' },
                { key: 'mild', label: '🟢 Nhẹ' },
                { key: 'moderate', label: '🟡 TB' },
                { key: 'severe', label: '🔴 Nặng' },
              ] as { key: SeverityLevel; label: string }[]).map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setLevel(opt.key)}
                  className={cn(
                    'px-3 py-2.5 text-sm font-medium transition border-l border-neutral-300 first:border-l-0',
                    level === opt.key
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-neutral-700 hover:bg-neutral-50'
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          )}

          {/* Disease Info */}
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
            <p className="text-sm">
              <span className="font-semibold text-blue-900">Bệnh:</span>{' '}
              <span className="text-blue-800">{matrix.disease_name}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Supply Norms Table */}
      <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-neutral-200">
          <h3 className="font-semibold text-neutral-900">
            Định mức thuốc/vật tư - {matrix.disease_name}
          </h3>
          <p className="text-xs text-neutral-500 mt-1">
            Hiển thị số lượng cần cho 1 ca bệnh ở mỗi cấp độ
            {' · '}
            <span className="font-medium text-neutral-700">
              {filteredSupplies.length}
            </span>{' '}
            / {matrix.supplies.length} mục
            {level !== 'all' && (
              <>
                {' · cấp độ: '}
                <span className="font-medium text-neutral-700">
                  {level === 'mild' ? '🟢 Nhẹ' : level === 'moderate' ? '🟡 Trung bình' : '🔴 Nặng'}
                </span>
              </>
            )}
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-b border-neutral-100 bg-neutral-50">
                <th className="text-left px-4 py-3 font-semibold">Mã</th>
                <th className="text-left px-4 py-3 font-semibold">Tên Hoạt chất / Vật tư</th>
                <th className="text-left px-4 py-3 font-semibold">Nhóm</th>
                <th className="text-left px-4 py-3 font-semibold">ĐVT</th>
                {showMild && (
                  <th className="text-center px-4 py-3 font-semibold">
                    <span className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs">
                      🟢 Nhẹ
                    </span>
                  </th>
                )}
                {showModerate && (
                  <th className="text-center px-4 py-3 font-semibold">
                    <span className="inline-flex items-center gap-1 px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs">
                      🟡 TB
                    </span>
                  </th>
                )}
                {showSevere && (
                  <th className="text-center px-4 py-3 font-semibold">
                    <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded text-xs">
                      🔴 Nặng
                    </span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {filteredSupplies.length === 0 ? (
                <tr>
                  <td
                    colSpan={4 + [showMild, showModerate, showSevere].filter(Boolean).length}
                    className="px-4 py-10 text-center text-neutral-500"
                  >
                    Không tìm thấy thuốc/vật tư phù hợp với bộ lọc.
                  </td>
                </tr>
              ) : (
                filteredSupplies.map((supply, idx) => (
                  <tr
                    key={supply.supply_id}
                    className={cn(
                      'border-b border-neutral-100 hover:bg-neutral-50 transition',
                      idx % 2 === 0 ? 'bg-white' : 'bg-neutral-50/50'
                    )}
                  >
                    <td className="px-4 py-3 font-mono text-neutral-700">{supply.supply_code}</td>
                    <td className="px-4 py-3 text-neutral-900">
                      <div className="font-medium">{supply.ten_hoat_chat}</div>
                      {supply.drug_code && (
                        <div className="text-xs text-neutral-500">{supply.drug_code}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-block px-2 py-1 bg-neutral-100 text-neutral-700 rounded text-xs">
                        {supply.group_name || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-neutral-600">{supply.unit}</td>
                    {showMild && (
                      <td className="px-4 py-3 text-center">
                        <span className="inline-block px-2.5 py-1 bg-emerald-100 text-emerald-900 font-semibold rounded">
                          {supply.mild}
                        </span>
                      </td>
                    )}
                    {showModerate && (
                      <td className="px-4 py-3 text-center">
                        <span className="inline-block px-2.5 py-1 bg-amber-100 text-amber-900 font-semibold rounded">
                          {supply.moderate}
                        </span>
                      </td>
                    )}
                    {showSevere && (
                      <td className="px-4 py-3 text-center">
                        <span className="inline-block px-2.5 py-1 bg-red-100 text-red-900 font-semibold rounded">
                          {supply.severe}
                        </span>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Guide */}
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
        <div className="flex gap-3">
          <TrendingUp className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-blue-900 mb-2">📝 Hướng dẫn sử dụng</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>
                <span className="font-medium">🟢 Cột Nhẽ:</span> Số lượng thuốc/vật tư cần cho 1 ca bệnh nhẹ
              </li>
              <li>
                <span className="font-medium">🟡 Cột Trung bình:</span> Số lượng cần cho 1 ca bệnh trung bình
              </li>
              <li>
                <span className="font-medium">🔴 Cột Nặng:</span> Số lượng cần cho 1 ca bệnh nặng
              </li>
              <li className="pt-1 border-t border-blue-200 mt-2">
                <span className="font-medium">Ví dụ:</span> Nếu dự báo 100 ca J20 (70% nhẹ, 25% TB, 5% nặng):
                <br />
                Paracetamol cần = (70×6) + (25×10) + (5×12) = 730 viên
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SupplyNormMatrix;
