import { Bell, Menu, User, LogOut, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useUIStore } from '../../store/uiStore';
import { useAuth } from '../../hooks/useAuth';
import { ROUTES, USER_ROLE_LABELS } from '../../utils/constants';
import { cn } from '../../utils/cn';

export default function Header() {
  const { pageTitle, toggleSidebar, unreadNotificationsCount } = useUIStore();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
  };

  const userInitials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .slice(-2)
        .join('')
        .toUpperCase()
    : 'U';

  return (
    <header className="flex items-center justify-between h-16 px-6 bg-white border-b border-neutral-200 shrink-0">
      {/* Left: Menu toggle + Page title */}
      <div className="flex items-center gap-4">
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-lg text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700 transition-colors lg:hidden"
          aria-label="Toggle sidebar"
        >
          <Menu size={20} />
        </button>
        <h1 className="text-lg font-semibold text-neutral-900">
          {pageTitle || 'MedForecast AI'}
        </h1>
      </div>

      {/* Right: Notifications + User */}
      <div className="flex items-center gap-3">
        {/* Notifications bell */}
        <button
          className="relative p-2 rounded-lg text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700 transition-colors"
          aria-label="Thông báo"
          onClick={() => navigate(ROUTES.ALERTS)}
        >
          <Bell size={20} />
          {unreadNotificationsCount > 0 && (
            <span className="absolute top-1 right-1 flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-danger-600 rounded-full">
              {unreadNotificationsCount > 9 ? '9+' : unreadNotificationsCount}
            </span>
          )}
        </button>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-neutral-100 transition-colors"
          >
            {/* Avatar */}
            <div className="flex items-center justify-center w-8 h-8 bg-primary-600 rounded-full text-white text-sm font-semibold">
              {userInitials}
            </div>
            {/* User info */}
            <div className="hidden sm:block text-left">
              <p className="text-sm font-medium text-neutral-900 leading-tight">
                {user?.full_name || 'Người dùng'}
              </p>
              <p className="text-xs text-neutral-500 leading-tight">
                {user?.role ? USER_ROLE_LABELS[user.role] : ''}
              </p>
            </div>
            <ChevronDown
              size={16}
              className={cn(
                'text-neutral-400 transition-transform',
                isUserMenuOpen && 'rotate-180'
              )}
            />
          </button>

          {/* Dropdown menu */}
          {isUserMenuOpen && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 z-10"
                onClick={() => setIsUserMenuOpen(false)}
              />
              <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border border-neutral-200 z-20 py-1">
                <div className="px-4 py-2 border-b border-neutral-100">
                  <p className="text-sm font-medium text-neutral-900 truncate">
                    {user?.full_name}
                  </p>
                  <p className="text-xs text-neutral-500 truncate">{user?.email}</p>
                </div>
                <button
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    navigate(ROUTES.SETTINGS);
                  }}
                  className="flex items-center gap-2 w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-50 transition-colors"
                >
                  <User size={16} />
                  Hồ sơ cá nhân
                </button>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2 w-full px-4 py-2 text-sm text-danger-600 hover:bg-danger-50 transition-colors"
                >
                  <LogOut size={16} />
                  Đăng xuất
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
