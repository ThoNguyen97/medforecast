import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Users,
  ShieldCheck,
  Boxes,
  AlertTriangle,
  Activity,
  Settings as SettingsIcon,
  Shield,
  Percent,
  Pill,
} from 'lucide-react';
import { useUIStore } from '../store/uiStore';
import { useAuthStore } from '../store/authStore';
import { ROUTES } from '../utils/constants';
import { cn } from '../utils/cn';
import UsersSection from '../components/admin/UsersSection';
import RolesPermissionsSection from '../components/admin/RolesPermissionsSection';
import ConfigurationsSection from '../components/admin/ConfigurationsSection';
import ThresholdsAndRatiosSection from '../components/admin/ThresholdsAndRatiosSection';
import AuditLogsSection from '../components/admin/AuditLogsSection';
import SeverityRateSection from '../components/admin/SeverityRateSection';
import SupplyNormSection from '../components/admin/SupplyNormSection';

type TabKey =
  | 'users'
  | 'roles'
  | 'configurations'
  | 'thresholds'
  | 'severity-rates'
  | 'supply-norms'
  | 'audit-logs';

const TABS: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'users', label: 'Quản lý tài khoản', icon: Users },
  { key: 'roles', label: 'Phân quyền', icon: ShieldCheck },
  { key: 'configurations', label: 'Cấu hình bệnh & khu vực', icon: Boxes },
  { key: 'severity-rates', label: 'Tỷ lệ Nhẹ/TB/Nặng', icon: Percent },
  { key: 'supply-norms', label: 'Định mức thuốc/vật tư', icon: Pill },
  { key: 'thresholds', label: 'Ngưỡng cảnh báo', icon: AlertTriangle },
  { key: 'audit-logs', label: 'Nhật ký hệ thống', icon: Activity },
];

/** Module 9 — Quản trị */
export default function Settings() {
  const { setPageTitle } = useUIStore();
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabKey>('users');

  useEffect(() => {
    setPageTitle('Quản trị hệ thống');
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
            Quản lý tài khoản, phân quyền, cấu hình bệnh, khu vực và các tham số hệ thống.
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
        {activeTab === 'configurations' && <ConfigurationsSection />}
        {activeTab === 'severity-rates' && <SeverityRateSection />}
        {activeTab === 'supply-norms' && <SupplyNormSection />}
        {activeTab === 'thresholds' && <ThresholdsAndRatiosSection />}
        {activeTab === 'audit-logs' && <AuditLogsSection />}
      </div>
    </div>
  );
}
