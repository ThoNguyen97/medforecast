import { Check, Minus } from 'lucide-react';
import { cn } from '../../utils/cn';

const ROLES = [
  { key: 'Administrator', label: 'Quản trị viên', tone: 'violet' },
  { key: 'Pharmacist', label: 'Bác sĩ / Dược sĩ', tone: 'blue' },
  { key: 'Inventory_Manager', label: 'Nhân viên kho', tone: 'emerald' },
  { key: 'Manager', label: 'Lãnh đạo / Quản lý', tone: 'amber' },
  { key: 'Viewer', label: 'Người xem', tone: 'neutral' },
];

const FEATURES: {
  group: string;
  items: { key: string; label: string; perms: Record<string, boolean> }[];
}[] = [
  {
    group: 'Dữ liệu & dự báo',
    items: [
      {
        key: 'epi-data',
        label: 'Xem & quản lý dữ liệu bệnh',
        perms: {
          Administrator: true,
          Pharmacist: true,
          Inventory_Manager: false,
          Manager: true,
          Viewer: true,
        },
      },
      {
        key: 'forecast',
        label: 'Phân tích & chạy dự báo',
        perms: {
          Administrator: true,
          Pharmacist: true,
          Inventory_Manager: false,
          Manager: true,
          Viewer: true,
        },
      },
    ],
  },
  {
    group: 'Vật tư & kho',
    items: [
      {
        key: 'inventory',
        label: 'Quản lý tồn kho',
        perms: {
          Administrator: true,
          Pharmacist: false,
          Inventory_Manager: true,
          Manager: true,
          Viewer: true,
        },
      },
      {
        key: 'alerts',
        label: 'Xem cảnh báo & tạo kế hoạch nhập kho',
        perms: {
          Administrator: true,
          Pharmacist: false,
          Inventory_Manager: true,
          Manager: true,
          Viewer: true,
        },
      },
      {
        key: 'approve-plan',
        label: 'Duyệt kế hoạch nhập kho',
        perms: {
          Administrator: true,
          Pharmacist: false,
          Inventory_Manager: false,
          Manager: true,
          Viewer: false,
        },
      },
    ],
  },
  {
    group: 'Báo cáo & quản trị',
    items: [
      {
        key: 'reports',
        label: 'Xem & xuất báo cáo',
        perms: {
          Administrator: true,
          Pharmacist: true,
          Inventory_Manager: true,
          Manager: true,
          Viewer: true,
        },
      },
      {
        key: 'config',
        label: 'Cấu hình định mức vật tư',
        perms: {
          Administrator: true,
          Pharmacist: true,
          Inventory_Manager: false,
          Manager: false,
          Viewer: false,
        },
      },
      {
        key: 'admin',
        label: 'Quản lý tài khoản & phân quyền',
        perms: {
          Administrator: true,
          Pharmacist: false,
          Inventory_Manager: false,
          Manager: false,
          Viewer: false,
        },
      },
    ],
  },
];

const TONE_BG: Record<string, string> = {
  violet: 'bg-violet-50 text-violet-700 border-violet-100',
  blue: 'bg-blue-50 text-blue-700 border-blue-100',
  emerald: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  amber: 'bg-amber-50 text-amber-700 border-amber-100',
  neutral: 'bg-neutral-100 text-neutral-700 border-neutral-200',
};

export default function RolesPermissionsSection() {
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-100">
        <h3 className="text-sm font-semibold text-neutral-900">
          Ma trận phân quyền theo vai trò
        </h3>
        <p className="text-xs text-neutral-500 mt-0.5">
          Bảng tổng hợp quyền truy cập từng chức năng tương ứng với 5 vai trò chuẩn
          theo spec 9.3.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-neutral-500 text-[11px] uppercase tracking-wider border-b border-neutral-100">
              <th className="text-left px-5 py-3 font-semibold w-[280px]">Chức năng</th>
              {ROLES.map((r) => (
                <th key={r.key} className="px-3 py-3 font-semibold text-center">
                  <span
                    className={cn(
                      'inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold border',
                      TONE_BG[r.tone],
                    )}
                  >
                    {r.label}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((g) => (
              <>
                <tr key={`group-${g.group}`} className="bg-neutral-50/60">
                  <td
                    colSpan={ROLES.length + 1}
                    className="px-5 py-2.5 text-[11px] font-bold text-neutral-500 uppercase tracking-wider"
                  >
                    {g.group}
                  </td>
                </tr>
                {g.items.map((it) => (
                  <tr key={it.key} className="border-t border-neutral-100">
                    <td className="px-5 py-3 text-neutral-700">{it.label}</td>
                    {ROLES.map((r) => {
                      const has = it.perms[r.key];
                      return (
                        <td key={r.key} className="px-3 py-3 text-center">
                          {has ? (
                            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-50 text-emerald-600">
                              <Check className="w-3.5 h-3.5" />
                            </span>
                          ) : (
                            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-neutral-100 text-neutral-400">
                              <Minus className="w-3.5 h-3.5" />
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-5 py-3 border-t border-neutral-100 bg-amber-50/40 text-xs text-amber-700">
        Ghi chú: Vai trò <strong>Lãnh đạo</strong> và <strong>Người xem</strong> sẽ
        được áp dụng khi backend mở rộng UserRole. Hiện hệ thống đang dùng 3 vai trò
        chuẩn (Administrator, Pharmacist, Inventory_Manager).
      </div>
    </div>
  );
}
