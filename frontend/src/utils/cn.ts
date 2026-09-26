/** Nối className có điều kiện (thay thế gọn cho clsx/classnames). */
export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ');
}
