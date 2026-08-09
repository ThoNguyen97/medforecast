import { ChevronDown, Search, Calendar, Stethoscope, MapPin } from 'lucide-react';
import { cn } from '../../utils/cn';
import type { ReportKind } from './ReportTypePicker';

export interface ReportFilterState {
  search: string; // Chỉ dùng cho các báo cáo khác, không dùng cho epidemic
  startMonth: string; // Cho báo cáo epidemic
  endMonth: string; // Cho báo cáo epidemic
  diseaseType: string;
  region: string;
  category: string;
  status: string;
}

interface Props {
  kind: ReportKind;
  state: ReportFilterState;
  onChange: (state: ReportFilterState) => void;
  diseases: { key: string; label: string }[];
  regions: string[];
}

export default function ReportFilterPanel({
  kind,
  state,
  onChange,
  diseases,
  regions,
}: Props) {
  const update = (patch: Partial<ReportFilterState>) =>
    onChange({ ...state, ...patch });

  const showDisease = ['epidemic', 'forecast', 'accuracy'].includes(kind);
  const showRegion = ['epidemic', 'forecast'].includes(kind);
  const showStatus = kind === 'inventory'; // Chỉ hiện ở báo cáo Tồn kho

  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">
        Bộ lọc báo cáo
      </p>
      <div className="space-y-4">
        {/* Thanh tìm kiếm hoặc bộ lọc tháng */}
        {(kind === 'epidemic' || kind === 'forecast') ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Month range */}
            <div>
              <label className="block text-sm font-medium text-neutral-600 mb-1.5">
                Khoảng thời gian
              </label>
              <div className="space-y-2">
                <div className="flex items-center gap-1">
                  <Calendar className="w-4 h-4 text-neutral-400 shrink-0" />
                  <input
                    type="month"
                    value={state.startMonth}
                    onChange={(e) => update({ startMonth: e.target.value })}
                    placeholder="Từ tháng/năm"
                    className="flex-1 px-3 py-2 border border-neutral-200 rounded-lg text-sm outline-none"
                  />
                </div>
                <div className="flex items-center gap-1">
                  <Calendar className="w-4 h-4 text-neutral-400 shrink-0" />
                  <input
                    type="month"
                    value={state.endMonth}
                    onChange={(e) => update({ endMonth: e.target.value })}
                    placeholder="Đến tháng/năm"
                    className="flex-1 px-3 py-2 border border-neutral-200 rounded-lg text-sm outline-none"
                  />
                </div>
              </div>
            </div>

            {/* Disease */}
            {showDisease && (
              <div>
                <label className="block text-sm font-medium text-neutral-600 mb-1.5">
                  Loại bệnh
                </label>
                <div className="relative">
                  <Stethoscope className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                  <select
                    value={state.diseaseType}
                    onChange={(e) => update({ diseaseType: e.target.value })}
                    className="w-full pl-9 pr-9 py-2 border border-neutral-200 rounded-lg text-sm appearance-none bg-white"
                  >
                    <option value="all">Tất cả các bệnh</option>
                    {diseases.map((d) => (
                      <option key={d.key} value={d.key}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400 pointer-events-none" />
                </div>
              </div>
            )}

            {/* Region (Tỉnh/Thành) */}
            {showRegion && (
              <div>
                <label className="block text-sm font-medium text-neutral-600 mb-1.5">
                  Tỉnh/Thành
                </label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                  <select
                    value={state.region}
                    onChange={(e) => update({ region: e.target.value })}
                    className="w-full pl-9 pr-9 py-2 border border-neutral-200 rounded-lg text-sm appearance-none bg-white"
                  >
                    <option value="all">Tất cả tỉnh/thành</option>
                    {regions.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400 pointer-events-none" />
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
            <input
              type="text"
              value={state.search}
              onChange={(e) => update({ search: e.target.value })}
              placeholder="Tìm kiếm theo tên bệnh, khu vực, vật tư..."
              className="w-full h-10 pl-9 pr-3 rounded-lg border border-neutral-300 bg-white text-sm placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            />
          </div>
        )}

        {/* Các bộ lọc khác - chỉ hiển thị cho các báo cáo không phải epidemic và forecast */}
        {kind !== 'epidemic' && kind !== 'forecast' && (
          <div className="flex flex-wrap items-center gap-2.5">
            {showDisease && (
              <label className="inline-flex items-center gap-2 text-sm text-neutral-600">
                Bệnh dịch:
                <div className="relative">
                  <select
                    value={state.diseaseType}
                    onChange={(e) => update({ diseaseType: e.target.value })}
                    className={cn(
                      'appearance-none h-10 pl-3 pr-8 rounded-lg border border-neutral-200 bg-white',
                      'text-sm font-medium text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500',
                    )}
                  >
                    <option value="all">Tất cả bệnh</option>
                    {diseases.map((d) => (
                      <option key={d.key} value={d.key}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                </div>
              </label>
            )}

            {showRegion && (
              <label className="inline-flex items-center gap-2 text-sm text-neutral-600">
                Khu vực:
                <div className="relative">
                  <select
                    value={state.region}
                    onChange={(e) => update({ region: e.target.value })}
                    className={cn(
                      'appearance-none h-10 pl-3 pr-8 rounded-lg border border-neutral-200 bg-white',
                      'text-sm font-medium text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500',
                    )}
                  >
                    <option value="all">Toàn thành phố</option>
                    {regions.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                </div>
              </label>
            )}

            {showStatus && (
              <label className="inline-flex items-center gap-2 text-sm text-neutral-600">
                Trạng thái:
                <div className="relative">
                  <select
                    value={state.status}
                    onChange={(e) => update({ status: e.target.value })}
                    className={cn(
                      'appearance-none h-10 pl-3 pr-8 rounded-lg border border-neutral-200 bg-white',
                      'text-sm font-medium text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500',
                    )}
                  >
                    <option value="all">Tất cả</option>
                    <option value="normal">An toàn</option>
                    <option value="low">Dưới ngưỡng</option>
                    <option value="critical">Cần nhập gấp</option>
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                </div>
              </label>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
