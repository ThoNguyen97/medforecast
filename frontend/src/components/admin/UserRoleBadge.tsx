import { cn } from '../../utils/cn';
import type { UserRole } from '../../services/usersService';

const ROLE_CFG: Record<
  UserRole,
  { label: string; bg: string; text: string; dot: string }
> = {
  Administrator: {
    label: 'Quản trị viên',
    bg: 'bg-violet-50',
    text: 'text-violet-700',
    dot: 'bg-violet-500',
  },
  Pharmacist: {
    label: 'Bác sĩ / Dược sĩ',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    dot: 'bg-blue-500',
  },
  Inventory_Manager: {
    label: 'Nhân viên kho',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    dot: 'bg-emerald-500',
  },
};

export default function UserRoleBadge({ role }: { role: UserRole }) {
  const cfg = ROLE_CFG[role] ?? ROLE_CFG.Pharmacist;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold',
        cfg.bg,
        cfg.text,
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', cfg.dot)} />
      {cfg.label}
    </span>
  );
}

export const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'Administrator', label: 'Quản trị viên' },
  { value: 'Pharmacist', label: 'Bác sĩ / Dược sĩ' },
  { value: 'Inventory_Manager', label: 'Nhân viên kho' },
];
