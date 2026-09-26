/** Chart theme dùng chung cho recharts. Palette đã kiểm định trên nền trắng (CVD ΔE ≥ 8);
 *  gán màu theo thứ tự cố định, màu trạng thái không dùng làm màu series. */

/** Series categorical, thứ tự cố định. */
export const SERIES = {
  s1: '#2a78d6', // series chính
  s2: '#008300',
  s3: '#e87ba4',
  s4: '#eda100',
  s5: '#1baf7a',
  s6: '#eb6834',
} as const;

/** Màu trung tính cho trục/lưới/nhãn. */
export const INK = {
  axis: '#6b7280',
  grid: '#e5e7eb',
  muted: '#9ca3af',
  reference: '#c7cdd6', // năm trước, baseline
} as const;

/** Props dùng chung cho mọi chart. */
export const gridProps = {
  stroke: INK.grid,
  strokeDasharray: '3 3',
  vertical: false,
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

