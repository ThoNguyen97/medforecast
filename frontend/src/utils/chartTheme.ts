/**
 * Chart theme chuẩn hóa cho toàn hệ thống (recharts).
 *
 * Palette categorical đã VALIDATE bằng bộ kiểm tra dataviz (CVD ΔE ≥ 8,
 * normal-vision ΔE ≥ 15, lightness band, chroma floor) trên nền trắng.
 * Quy tắc: gán màu theo THỨ TỰ CỐ ĐỊNH, không xoay vòng; màu trạng thái
 * (status) dành riêng cho cảnh báo, không dùng làm màu series.
 */

/** Series categorical — thứ tự cố định slot 1→5 */
export const SERIES = {
  s1: '#2a78d6', // blue     — series chính (năm nay / thực tế / tồn kho)
  s2: '#008300', // green    — series 2
  s3: '#e87ba4', // magenta  — series 3
  s4: '#eda100', // yellow   — series 4
  s5: '#1baf7a', // aqua     — series 5
  s6: '#eb6834', // orange   — series 6
} as const;

export const SERIES_ORDER: string[] = [
  SERIES.s1,
  SERIES.s2,
  SERIES.s3,
  SERIES.s4,
  SERIES.s5,
];

/** Màu trạng thái — chỉ dùng cho cảnh báo/badge, luôn kèm icon hoặc nhãn */
export const STATUS = {
  good: '#16a34a',
  warning: '#d97706',
  serious: '#ea580c',
  critical: '#dc2626',
} as const;

/** Màu phụ trợ trung tính cho trục/lưới/nhãn — grid phải "lùi về sau" */
export const INK = {
  axis: '#6b7280', // text nhãn trục
  grid: '#e5e7eb', // đường lưới nhạt
  muted: '#9ca3af',
  reference: '#c7cdd6', // đường tham chiếu (năm trước, baseline)
} as const;

/** Props dùng chung cho recharts — áp cho mọi chart để đồng nhất */
export const gridProps = {
  stroke: INK.grid,
  strokeDasharray: '3 3',
  vertical: false,
} as const;

export const axisProps = {
  stroke: 'transparent',
  tickLine: false,
  axisLine: false,
  tick: { fill: INK.axis, fontSize: 12 },
} as const;

export const tooltipStyle = {
  contentStyle: {
    background: '#ffffff',
    border: '1px solid #e5e7eb',
    borderRadius: 10,
    boxShadow: '0 4px 12px rgba(15, 23, 42, 0.08)',
    fontSize: 12,
    padding: '8px 12px',
  },
  labelStyle: { color: '#111827', fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: '#374151', padding: 0 },
  cursor: { stroke: '#cbd5e1', strokeWidth: 1 },
} as const;

export const legendStyle = {
  iconSize: 8,
  wrapperStyle: { fontSize: 12, color: '#4b5563' },
} as const;

/** Độ dày line chuẩn 2px, marker ≥ 3px radius */
export const LINE_WIDTH = 2;
export const DOT_RADIUS = 3;
