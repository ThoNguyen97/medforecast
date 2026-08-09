import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  TrendingUp, Package, AlertTriangle, CloudSun, Loader2, RefreshCw, CheckCircle2,
} from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { useAuthStore } from '../store/authStore';
import { forecastHierService } from '../services/forecastHierService';
import { useHierForecast, useSupplyPlan } from '../hooks/useForecastHier';

const METHOD_LABELS: Record<string, string> = {
  top_down_dynamic: 'Phân cấp — tỷ trọng động (khuyến nghị)',
  top_down_fixed: 'Phân cấp — tỷ trọng cố định',
  bottom_up: 'Bottom-up',
  mint: 'Hòa giải MinT',
};

export default function SupplyPlanning() {
  const { setPageTitle } = useUIStore();
  const { isAuthenticated } = useAuthStore();
  const [block, setBlock] = useState<string>('');
  const [method, setMethod] = useState<string>('top_down_dynamic');

  useEffect(() => setPageTitle('Kế hoạch nhập kho'), [setPageTitle]);

  const { data: blocks } = useQuery({
    queryKey: ['forecast-hier', 'blocks'],
    queryFn: () => forecastHierService.blocks(),
    enabled: isAuthenticated,
    retry: false,
  });

  useEffect(() => {
    if (!block && blocks && blocks.length) setBlock(blocks[0]);
  }, [blocks, block]);

  const forecast = useHierForecast(block, method);
  const plan = useSupplyPlan(block, method);
  const loading = forecast.isLoading || plan.isLoading;

  const refetch = () => {
    forecast.refetch();
    plan.refetch();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-extrabold text-neutral-900">Kế hoạch nhập kho</h2>
          <p className="text-sm text-neutral-500 mt-1">
            Dự báo phân cấp theo nhóm bệnh → đề xuất nhập vật tư (có mức an toàn)
          </p>
        </div>
        <button
          type="button"
          onClick={refetch}
          disabled={loading || !block}
          className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-neutral-200 rounded-xl text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-60"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Làm mới
        </button>
      </div>

      {/* Bộ chọn */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-neutral-500">Nhóm bệnh:</span>
          <div className="flex gap-1.5">
            {(blocks ?? []).map((b) => (
              <button
                key={b}
                onClick={() => setBlock(b)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${
                  block === b
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-neutral-700 border-neutral-200 hover:bg-neutral-50'
                }`}
              >
                {b}
              </button>
            ))}
          </div>
        </div>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-sm border border-neutral-200 bg-white text-neutral-700"
        >
          {Object.entries(METHOD_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-neutral-500 py-10 justify-center">
          <Loader2 className="w-5 h-5 animate-spin" /> Đang tính dự báo & đề xuất...
        </div>
      )}

      {/* Thẻ dự báo nhóm */}
      {!loading && forecast.data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white border border-neutral-200 rounded-xl p-5">
            <div className="flex items-center gap-2 text-neutral-500 text-sm mb-1">
              <TrendingUp className="w-4 h-4" /> Dự báo ca — {forecast.data.target_period}
            </div>
            <div className="text-3xl font-extrabold text-neutral-900">
              {forecast.data.group_forecast}
            </div>
            <div className="text-sm text-neutral-500 mt-1">
              Khoảng: {forecast.data.group_interval.lower}–{forecast.data.group_interval.upper}
            </div>
          </div>
          <div className="bg-white border border-neutral-200 rounded-xl p-5">
            <div className="text-neutral-500 text-sm mb-2">Chia theo mã (điểm / an toàn)</div>
            <div className="space-y-1">
              {Object.keys(forecast.data.by_code).map((c) => (
                <div key={c} className="flex justify-between text-sm">
                  <span className="font-medium text-neutral-700">{c}</span>
                  <span className="text-neutral-600">
                    {forecast.data!.by_code[c]} / {forecast.data!.by_code_upper[c]}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-white border border-neutral-200 rounded-xl p-5">
            <div className="text-neutral-500 text-sm mb-2">Yếu tố mô hình</div>
            <div className="flex items-center gap-2 text-sm">
              <CloudSun className="w-4 h-4 text-amber-500" />
              {forecast.data.weather_used ? 'Có dùng thời tiết' : 'Chưa có thời tiết'}
            </div>
            {plan.data && (
              <div className="mt-3 text-sm text-neutral-600">
                {plan.data.n_shortage}/{plan.data.n_supplies} vật tư cần nhập thêm
              </div>
            )}
          </div>
        </div>
      )}

      {/* Bảng đề xuất nhập kho */}
      {!loading && plan.data && (
        <div className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-4 border-b border-neutral-100">
            <Package className="w-5 h-5 text-blue-600" />
            <h3 className="font-semibold text-neutral-900">Đề xuất nhập kho</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-neutral-50 text-neutral-500">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Vật tư</th>
                  <th className="text-right px-4 py-2 font-medium">Nhu cầu</th>
                  <th className="text-right px-4 py-2 font-medium">Mức an toàn</th>
                  <th className="text-right px-4 py-2 font-medium">Tồn kho</th>
                  <th className="text-right px-4 py-2 font-medium">Đề xuất nhập</th>
                  <th className="text-right px-4 py-2 font-medium">Lead (ngày)</th>
                  <th className="text-center px-4 py-2 font-medium">Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {plan.data.items.map((it) => (
                  <tr key={it.supply_code} className="border-t border-neutral-100">
                    <td className="px-4 py-2">
                      <div className="font-medium text-neutral-800">{it.name}</div>
                      <div className="text-xs text-neutral-400">{it.group_name}</div>
                    </td>
                    <td className="px-4 py-2 text-right text-neutral-600">{it.demand_forecast}</td>
                    <td className="px-4 py-2 text-right text-neutral-800 font-medium">{it.safety_level}</td>
                    <td className="px-4 py-2 text-right text-neutral-600">{it.current_stock}</td>
                    <td className="px-4 py-2 text-right font-semibold text-neutral-900">{it.suggested_import}</td>
                    <td className="px-4 py-2 text-right text-neutral-500">{it.lead_time_days}</td>
                    <td className="px-4 py-2 text-center">
                      {it.status === 'shortage' ? (
                        <span className="inline-flex items-center gap-1 text-red-600 text-xs font-medium">
                          <AlertTriangle className="w-3.5 h-3.5" /> Cần nhập
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-green-600 text-xs font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Đủ
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
