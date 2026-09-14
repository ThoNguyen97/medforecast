/**
 * Format a number with thousand separators
 */
export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Format a number as Vietnamese currency (VND)
 */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Format a date string to Vietnamese locale
 */
export function formatDate(dateString: string, options?: Intl.DateTimeFormatOptions): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...options,
  }).format(date);
}

/**
 * Format a date string with time
 */
export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

/**
 * Format a date as relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'Vừa xong';
  if (diffMinutes < 60) return `${diffMinutes} phút trước`;
  if (diffHours < 24) return `${diffHours} giờ trước`;
  if (diffDays < 7) return `${diffDays} ngày trước`;
  return formatDate(dateString);
}

/**
 * Format a percentage value
 */
export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format a quantity with unit
 */
export function formatQuantity(value: number, unit: string): string {
  return `${formatNumber(value)} ${unit}`;
}

/**
 * Truncate a string to a maximum length
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

/**
 * Câu lỗi mà máy chủ thật sự trả về (FastAPI đặt ở `detail`).
 *
 * 12/09/2026: nút Đồng bộ HIS bắt lỗi rồi hiện "Đồng bộ thất bại" — nuốt mất
 * câu hướng dẫn duy nhất người dùng cần ("Chưa cấu hình kết nối HIS. Vào Quản
 * trị → Kết nối HIS…"). Dùng hàm này thay cho chuỗi cố định.
 */
export function loiMayChu(e: unknown, macDinh = 'Có lỗi xảy ra'): string {
  const err = e as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    // lỗi kiểm tra dữ liệu của FastAPI: [{loc, msg, type}, …]
    const msg = (detail[0] as { msg?: string })?.msg;
    if (msg) return msg;
  }
  return err?.message || macDinh;
}

/**
 * Chuỗi thời gian do máy chủ trả về → Date đúng múi giờ.
 *
 * SQLite ghi `CURRENT_TIMESTAMP` theo **UTC**, còn `datetime.isoformat()` của
 * Python KHÔNG kèm offset ("2026-09-13T10:22:33"). Theo chuẩn ECMAScript,
 * chuỗi date-time không offset bị hiểu là GIỜ ĐỊA PHƯƠNG → ở Việt Nam hiển thị
 * lệch đúng 7 tiếng. Hàm này gắn 'Z' khi chuỗi thiếu offset để luôn quy về UTC
 * rồi mới đổi sang giờ máy người dùng.
 */
export function parseThoiGianMayChu(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const s = String(iso).trim();
  if (!s) return null;
  const coOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(s);
  const d = new Date(coOffset ? s : `${s.replace(' ', 'T')}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** ISO máy chủ → "dd/mm/yyyy hh:mm" giờ địa phương; `khiTrong` nếu không có. */
export function formatThoiGianMayChu(
  iso: string | null | undefined,
  khiTrong = '—',
): string {
  const d = parseThoiGianMayChu(iso);
  if (!d) return khiTrong;
  return d.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
}
