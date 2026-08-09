import { useMemo, useState } from 'react';
import { Plus, Search, Loader2, Lock, Unlock, Pencil, Trash2 } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import {
  useCreateUser,
  useDeleteUser,
  useToggleUserActive,
  useUpdateUser,
  useUsers,
} from '../../hooks/useUsers';
import type { User } from '../../types/auth';
import UserRoleBadge, { ROLE_OPTIONS } from './UserRoleBadge';
import UserFormDialog, { type UserFormValues } from './UserFormDialog';

export default function UsersSection() {
  const { user: currentUser } = useAuthStore();
  const { data: users = [], isLoading } = useUsers();
  const createMut = useCreateUser();
  const updateMut = useUpdateUser();
  const deleteMut = useDeleteUser();
  const toggleMut = useToggleUserActive();

  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<User | null>(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return users.filter((u) => {
      if (q && !`${u.username} ${u.email} ${u.full_name ?? ''}`.toLowerCase().includes(q)) {
        return false;
      }
      if (roleFilter !== 'all' && u.role !== roleFilter) return false;
      return true;
    });
  }, [users, search, roleFilter]);

  const counts = useMemo(() => {
    const active = users.filter((u) => u.is_active).length;
    return { total: users.length, active, locked: users.length - active };
  }, [users]);

  const onSubmitForm = async (values: UserFormValues) => {
    if (editing) {
      await updateMut.mutateAsync({
        id: editing.id,
        payload: {
          email: values.email,
          full_name: values.full_name || null,
          role: values.role,
          is_active: values.is_active,
        },
      });
    } else {
      await createMut.mutateAsync({
        username: values.username,
        email: values.email,
        full_name: values.full_name || null,
        role: values.role,
        password: values.password,
      });
    }
  };

  const onConfirmDelete = async () => {
    if (!confirmDelete) return;
    await deleteMut.mutateAsync(confirmDelete.id);
    setConfirmDelete(null);
  };

  return (
    <div className="space-y-5">
      {/* Mini KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <KpiTile label="Tổng tài khoản" value={counts.total} />
        <KpiTile label="Đang hoạt động" value={counts.active} tone="success" />
        <KpiTile label="Đã khoá" value={counts.locked} tone={counts.locked > 0 ? 'warning' : 'default'} />
      </div>

      {/* Toolbar + table */}
      <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-neutral-100">
          <div className="flex flex-wrap items-center gap-2.5 flex-1">
            <div className="relative flex-1 min-w-[220px] max-w-md">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Tìm theo tên đăng nhập, email, họ tên..."
                className="w-full h-10 pl-9 pr-3 rounded-lg border border-neutral-200 bg-neutral-50 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
              />
            </div>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="h-10 px-3 rounded-lg border border-neutral-200 bg-white text-sm font-medium text-neutral-700 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500"
            >
              <option value="all">Tất cả vai trò</option>
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Thêm tài khoản
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-y border-neutral-100">
                <th className="text-left px-5 py-3 font-semibold">Tài khoản</th>
                <th className="text-left px-5 py-3 font-semibold">Email</th>
                <th className="text-left px-5 py-3 font-semibold">Vai trò</th>
                <th className="text-left px-5 py-3 font-semibold">Trạng thái</th>
                <th className="text-right px-5 py-3 font-semibold">Hành động</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="py-10">
                    <div className="flex items-center justify-center gap-2 text-neutral-500 text-sm">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Đang tải danh sách tài khoản...
                    </div>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-sm text-neutral-400">
                    Không tìm thấy tài khoản phù hợp
                  </td>
                </tr>
              ) : (
                filtered.map((u) => (
                  <tr key={u.id} className="border-t border-neutral-100 hover:bg-neutral-50/60">
                    <td className="px-5 py-3.5">
                      <p className="text-neutral-900 font-semibold leading-tight">
                        {u.full_name || u.username}
                      </p>
                      <p className="text-xs text-neutral-400 mt-0.5">@{u.username}</p>
                    </td>
                    <td className="px-5 py-3.5 text-neutral-700">{u.email}</td>
                    <td className="px-5 py-3.5">
                      <UserRoleBadge role={u.role as any} />
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusPill active={u.is_active} />
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center justify-end gap-1">
                        <IconButton
                          title={u.is_active ? 'Khoá tài khoản' : 'Mở khoá'}
                          onClick={() =>
                            toggleMut.mutate({ id: u.id, is_active: !u.is_active })
                          }
                          disabled={u.id === currentUser?.id}
                        >
                          {u.is_active ? (
                            <Lock className="w-4 h-4 text-amber-600" />
                          ) : (
                            <Unlock className="w-4 h-4 text-emerald-600" />
                          )}
                        </IconButton>
                        <IconButton
                          title="Chỉnh sửa"
                          onClick={() => {
                            setEditing(u);
                            setDialogOpen(true);
                          }}
                        >
                          <Pencil className="w-4 h-4 text-blue-600" />
                        </IconButton>
                        <IconButton
                          title="Xoá"
                          onClick={() => setConfirmDelete(u)}
                          disabled={u.id === currentUser?.id}
                        >
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </IconButton>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Form dialog */}
      <UserFormDialog
        open={dialogOpen}
        initial={editing}
        onClose={() => setDialogOpen(false)}
        onSubmit={onSubmitForm}
      />

      {/* Confirm delete */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-base font-semibold text-neutral-900">
              Xác nhận xoá tài khoản
            </h3>
            <p className="text-sm text-neutral-500 mt-2">
              Tài khoản{' '}
              <span className="font-semibold text-neutral-700">
                {confirmDelete.full_name || confirmDelete.username}
              </span>{' '}
              sẽ bị xoá khỏi hệ thống. Hành động này không thể hoàn tác.
            </p>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 text-sm font-medium text-neutral-700 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50"
              >
                Huỷ
              </button>
              <button
                type="button"
                onClick={onConfirmDelete}
                disabled={deleteMut.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-60"
              >
                {deleteMut.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                Xoá tài khoản
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiTile({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: number;
  tone?: 'default' | 'success' | 'warning';
}) {
  const color =
    tone === 'success'
      ? 'text-emerald-700'
      : tone === 'warning'
      ? 'text-amber-700'
      : 'text-neutral-900';
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <p className={`text-3xl font-extrabold tabular-nums mt-1 ${color}`}>
        {value.toLocaleString('vi-VN')}
      </p>
    </div>
  );
}

function StatusPill({ active }: { active: boolean }) {
  return (
    <span
      className={
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold ' +
        (active
          ? 'bg-emerald-50 text-emerald-700'
          : 'bg-neutral-100 text-neutral-500')
      }
    >
      <span
        className={
          'w-1.5 h-1.5 rounded-full shrink-0 ' +
          (active ? 'bg-emerald-500' : 'bg-neutral-400')
        }
      />
      {active ? 'Hoạt động' : 'Đã khoá'}
    </span>
  );
}

function IconButton({
  title,
  disabled,
  onClick,
  children,
}: {
  title: string;
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className="p-1.5 rounded-md hover:bg-neutral-100 disabled:opacity-40 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}
