import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Users,
  ShieldCheck,
  Boxes,
  Activity,
  Settings as SettingsIcon,
  Shield,
  SlidersHorizontal,
  Scale,
  Database,
} from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { useAuthStore } from '../store/authStore';
import { ROUTES } from '../utils/constants';
import { cn } from '../utils/cn';
import UsersSection from '../components/admin/UsersSection';
import RolesPermissionsSection from '../components/admin/RolesPermissionsSection';
import ConfigurationsSection from '../components/admin/ConfigurationsSection';
import AuditLogsSection from '../components/admin/AuditLogsSection';
import HisConnectionSection from '../components/admin/HisConnectionSection';
import DssParamsSection from '../components/admin/DssParamsSection';
import EmpiricalNormsSection from '../components/admin/EmpiricalNormsSection';

// 12/09/2026: ba tab "Tỷ lệ Nhẹ/TB/Nặng", "Định mức thuốc", "Ngưỡng cảnh
// báo" đã gỡ — chúng sửa ba bảng mà DSS thật không đọc (định mức thực nghiệm
// thay cho nhập tay; ngưỡng thật là dss.thresholds 18/36 ngày DOI, không phải
// 3/7/14). Thay bằng "Tham số DSS" (sửa được) và "Định mức thực nghiệm" (chỉ đọc).
// Mã cũ ở _archive/dinh_muc_nhap_tay/.

type TabKey =
  | 'users'
  | 'roles'
  | 'his-connection'
  | 'configurations'
  | 'dss-params'
  | 'dss-norms'
  | 'audit-logs';

const TABS: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'users', label: 'Quản lý tài khoản', icon: Users },
  { key: 'roles', label: 'Phân quyền', icon: ShieldCheck },
  { key: 'his-connection', label: 'Kết nối HIS', icon: Database },
  { key: 'configurations', label: 'Cấu hình bệnh & khu vực', icon: Boxes },
  { key: 'dss-params', label: 'Tham số DSS', icon: SlidersHorizontal },
  { key: 'dss-norms', label: 'Định mức thực nghiệm', icon: Scale },
  { key: 'audit-logs', label: 'Nhật ký hệ thống', icon: Activity },
];

/** Module 9 — Quản trị */
export default function Settings() {
  const { setPageTitle } = useUIStore();
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabKey>('users');

  useEffect(() => {
    setPageTitle('Quản trị');
  }, [setPageTitle]);

  if (user && user.role !== 'Administrator') {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-3xl font-extrabold text-neutral-900">
              Quản trị hệ thống
            </h2>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-violet-50 text-violet-700 border border-violet-100">
              <Shield className="w-3 h-3" />
              Chỉ Quản trị viên
            </span>
          </div>
          <p className="text-sm text-neutral-500 mt-1">
            Tài khoản, phân quyền, kết nối HIS, cấu hình bệnh/khu vực và tham số của bộ máy DSS.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 text-xs text-neutral-500">
          <SettingsIcon className="w-4 h-4" />
          Module 9 — Quản trị
        </div>
      </div>

      {/* Tab nav */}
      <div className="bg-white rounded-2xl border border-neutral-200 p-1.5 flex flex-wrap gap-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setActiveTab(t.key)}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition',
                active
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-neutral-600 hover:bg-neutral-50',
              )}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'users' && <UsersSection />}
        {activeTab === 'roles' && <RolesPermissionsSection />}
        {activeTab === 'his-connection' && <HisConnectionSection />}
        {activeTab === 'configurations' && <ConfigurationsSection />}
        {activeTab === 'dss-params' && <DssParamsSection />}
        {activeTab === 'dss-norms' && <EmpiricalNormsSection />}
        {activeTab === 'audit-logs' && <AuditLogsSection />}
      </div>
    </div>
  );
}
