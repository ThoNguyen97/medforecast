/** Định dạng số có phân tách hàng nghìn. */
export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/** Định dạng tiền VND. */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

/** Định dạng ngày theo locale vi-VN. */
export function formatDate(dateString: string, options?: Intl.DateTimeFormatOptions): string {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...options,
  }).format(date);
}

/** Định dạng ngày kèm giờ. */
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

/** Thời gian tương đối (vd. "2 giờ trước"). */
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

/** Định dạng phần trăm. */
export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

/** Định dạng số lượng kèm đơn vị. */
export function formatQuantity(value: number, unit: string): string {
  return `${formatNumber(value)} ${unit}`;
}

/** Cắt chuỗi về độ dài tối đa. */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength)}...`;
}

/**
 * Thông điệp lỗi máy chủ trả về (FastAPI đặt ở `detail`).
 * Dùng thay cho chuỗi lỗi cố định để người dùng thấy hướng dẫn cụ thể từ backend.
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
 * SQLite ghi `CURRENT_TIMESTAMP` theo UTC và `datetime.isoformat()` không kèm
 * offset; ECMAScript hiểu chuỗi không offset là giờ địa phương (lệch 7 tiếng ở
 * Việt Nam). Hàm gắn 'Z' khi thiếu offset rồi đổi sang giờ máy người dùng.
 */
function parseThoiGianMayChu(iso: string | null | undefined): Date | null {
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
