import { useEffect, useState } from 'react';
import { X, Loader2 } from 'lucide-react';
import type { User } from '../../types/auth';
import type { UserRole } from '../../services/usersService';
import { ROLE_OPTIONS } from './UserRoleBadge';

export interface UserFormValues {
  id?: number;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  password: string;
  is_active: boolean;
}

interface Props {
  open: boolean;
  initial?: User | null;
  onClose: () => void;
  onSubmit: (values: UserFormValues) => Promise<void>;
}

export default function UserFormDialog({
  open,
  initial,
  onClose,
  onSubmit,
}: Props) {
  const isEdit = !!initial;
  const [values, setValues] = useState<UserFormValues>({
    username: '',
    email: '',
    full_name: '',
    role: 'Pharmacist',
    password: '',
    is_active: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initial) {
      setValues({
        id: initial.id,
        username: initial.username,
        email: initial.email,
        full_name: initial.full_name ?? '',
        role: (initial.role as UserRole) ?? 'Pharmacist',
        password: '',
        is_active: initial.is_active ?? true,
      });
    } else {
      setValues({
        username: '',
        email: '',
        full_name: '',
        role: 'Pharmacist',
        password: '',
        is_active: true,
      });
    }
    setError(null);
  }, [initial, open]);

  if (!open) return null;

  const update = (patch: Partial<UserFormValues>) =>
    setValues((v) => ({ ...v, ...patch }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!isEdit && values.password.length < 8) {
      setError('Mật khẩu phải có ít nhất 8 ký tự');
      return;
    }
    try {
      setSubmitting(true);
      await onSubmit(values);
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Có lỗi xảy ra');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">
            {isEdit ? 'Chỉnh sửa tài khoản' : 'Thêm tài khoản mới'}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-500"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          <Field label="Tên đăng nhập" required>
            <input
              type="text"
              required
              disabled={isEdit}
              value={values.username}
              onChange={(e) => update({ username: e.target.value })}
              className={inputClass + (isEdit ? ' bg-neutral-50 text-neutral-500' : '')}
              placeholder="Ví dụ: bs_hieu"
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Họ và tên">
              <input
                type="text"
                value={values.full_name}
                onChange={(e) => update({ full_name: e.target.value })}
                className={inputClass}
                placeholder="Nguyễn Minh Hiếu"
              />
            </Field>
            <Field label="Email" required>
              <input
                type="email"
                required
                value={values.email}
                onChange={(e) => update({ email: e.target.value })}
                className={inputClass}
                placeholder="user@hospital.vn"
              />
            </Field>
          </div>

          <Field label="Vai trò" required>
            <select
              value={values.role}
              onChange={(e) => update({ role: e.target.value as UserRole })}
              className={inputClass}
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </Field>

          {!isEdit && (
            <Field label="Mật khẩu" required hint="Tối thiểu 8 ký tự">
              <input
                type="password"
                required
                minLength={8}
                value={values.password}
                onChange={(e) => update({ password: e.target.value })}
                className={inputClass}
                placeholder="••••••••"
              />
            </Field>
          )}

          {isEdit && (
            <label className="flex items-center gap-2 text-sm text-neutral-700">
              <input
                type="checkbox"
                checked={values.is_active}
                onChange={(e) => update({ is_active: e.target.checked })}
                className="rounded border-neutral-300"
              />
              Tài khoản đang hoạt động
            </label>
          )}

          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50"
            >
              Huỷ
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              {isEdit ? 'Lưu thay đổi' : 'Tạo tài khoản'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const inputClass =
  'w-full h-10 px-3 rounded-lg border border-neutral-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500';

function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-neutral-600 mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </span>
      {children}
      {hint && <p className="text-[11px] text-neutral-400 mt-1">{hint}</p>}
    </label>
  );
}
