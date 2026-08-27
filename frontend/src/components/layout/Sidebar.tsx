import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  HeartPulse,
  CloudSun,
  TrendingUp,
  Boxes,
  ShoppingCart,
  FileBarChart,
  Settings,
  HelpCircle,
  LogOut,
  Stethoscope,
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { ROUTES } from '../../utils/constants';
import { cn } from '../../utils/cn';

interface NavItem {
  label: string;
  path: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  adminOnly?: boolean;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', path: ROUTES.DASHBOARD, icon: LayoutDashboard },
  { label: 'Dữ liệu bệnh', path: ROUTES.EPIDEMIOLOGY, icon: HeartPulse },
  { label: 'Dữ liệu thời tiết', path: ROUTES.WEATHER, icon: CloudSun },
  { label: 'Phân tích & Dự báo', path: ROUTES.FORECASTING, icon: TrendingUp },
  { label: 'Vật tư y tế', path: ROUTES.INVENTORY, icon: Boxes },
  { label: 'Đề xuất nhập kho', path: ROUTES.ALERTS, icon: ShoppingCart },
  { label: 'Báo cáo', path: ROUTES.REPORTS, icon: FileBarChart },
  { label: 'Quản trị', path: ROUTES.SETTINGS, icon: Settings, adminOnly: true },
];

export default function Sidebar() {
  const { user, logout } = useAuthStore();
  const isAdmin = user?.role === 'Administrator';

  return (
    <aside className="flex flex-col h-full w-64 bg-white border-r border-neutral-200">
      {/* Logo */}
      <div className="flex items-center gap-3 h-20 px-5 shrink-0">
        <div className="flex items-center justify-center w-10 h-10 bg-blue-600 rounded-xl shrink-0">
          <Stethoscope size={20} className="text-white" />
        </div>
        <div className="min-w-0">
          <p className="font-bold text-sm text-neutral-900 leading-tight">MedForecast AI</p>
          <p className="text-xs text-neutral-500 leading-tight">Dự báo vật tư y tế</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3">
        <ul className="space-y-1">
          {navItems
            .filter((item) => !item.adminOnly || isAdmin)
            .map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    cn(
                      'relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-blue-50 text-blue-700 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-1 before:rounded-full before:bg-blue-600'
                        : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900',
                    )
                  }
                >
                  <item.icon size={18} className="shrink-0" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              </li>
            ))}
        </ul>
      </nav>

      {/* Footer actions */}
      <div className="border-t border-neutral-100 px-3 py-3 space-y-1">
        <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-neutral-600 hover:bg-neutral-50">
          <HelpCircle size={18} />
          Hỗ trợ
        </button>
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-neutral-600 hover:bg-neutral-50"
        >
          <LogOut size={18} />
          Đăng xuất
        </button>
      </div>
    </aside>
  );
}
