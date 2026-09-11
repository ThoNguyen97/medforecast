import { cn } from '../../utils/cn';
import { BLOCK_LABELS, LEVEL_LABELS, type AlertLevel, type BlockCode } from '../../types/dashboardV2';

export interface DashboardFilterState {
  block: BlockCode | 'all';
  focus: boolean;
  level: AlertLevel | null;
}

/**
 * Hàng bộ lọc. "Kỳ" là nhãn chỉ đọc: mọi KPI neo vào kỳ đã chốt gần nhất,
 * đổi kỳ là đổi mốc của cả hệ thống — không phải việc của một combobox.
 */
export default function DashboardFilters({
  value,
  onChange,
  lastClosed,
  openPeriod,
  focusCount,
  allCount,
}: {
  value: DashboardFilterState;
  onChange: (next: DashboardFilterState) => void;
  lastClosed: string | null;
  openPeriod: string | null;
  focusCount: number;
  allCount: number;
}) {
  const selectCls =
    'w-full h-9 rounded-lg border border-neutral-200 bg-white px-2.5 text-sm text-neutral-800 focus:outline-none focus:ring-2 focus:ring-blue-500/30';
  const labelCls = 'block text-[10.5px] uppercase tracking-wider text-neutral-500 font-semibold mb-1';

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 bg-white rounded-2xl border border-neutral-200 px-4 py-3">
      <div>
        <span className={labelCls}>Kỳ</span>
        <div className="h-9 flex items-center gap-2 text-sm">
          <span className="font-semibold text-neutral-900">{lastClosed ?? '—'}</span>
          <span className="text-neutral-400">đã chốt</span>
          {openPeriod && (
            <span className="ml-auto text-[11px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-100">
              {openPeriod} đang mở
            </span>
          )}
        </div>
      </div>
      <div>
        <label htmlFor="dash-block" className={labelCls}>
          Nhóm bệnh
        </label>
        <select
          id="dash-block"
          className={selectCls}
          value={value.block}
          onChange={(e) => onChange({ ...value, block: e.target.value as BlockCode | 'all' })}
        >
          <option value="all">Tất cả (3 khối hô hấp)</option>
          {(Object.keys(BLOCK_LABELS) as BlockCode[]).map((b) => (
            <option key={b} value={b}>
              {b} · {BLOCK_LABELS[b]}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="dash-focus" className={labelCls}>
          Tập vật tư
        </label>
        <select
          id="dash-focus"
          className={selectCls}
          value={value.focus ? 'focus' : 'all'}
          onChange={(e) => onChange({ ...value, focus: e.target.value === 'focus' })}
        >
          <option value="focus">Trọng tâm hô hấp · {focusCount.toLocaleString('vi-VN')} mã có mẫu số</option>
          <option value="all">Toàn danh mục · {allCount.toLocaleString('vi-VN')} mã có mẫu số</option>
        </select>
      </div>
      <div>
        <span className={labelCls}>Mức cảnh báo</span>
        <div className="h-9 flex items-center gap-1">
          {([null, 'red', 'amber', 'green', 'grey'] as Array<AlertLevel | null>).map((lv) => (
            <button
              key={lv ?? 'default'}
              type="button"
              onClick={() => onChange({ ...value, level: lv })}
              className={cn(
                'px-2.5 h-8 rounded-lg text-xs font-medium border transition',
                value.level === lv
                  ? 'bg-neutral-900 text-white border-neutral-900'
                  : 'bg-white text-neutral-600 border-neutral-200 hover:bg-neutral-50',
              )}
            >
              {lv ? LEVEL_LABELS[lv] : 'Đỏ + Vàng'}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
