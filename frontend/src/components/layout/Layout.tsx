import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useUIStore } from '../../store/uiStore';
import { cn } from '../../utils/cn';
import ErrorBoundary from '../common/ErrorBoundary';

export default function Layout() {
  const { isSidebarOpen } = useUIStore();
  const location = useLocation();

  return (
    <div className="flex h-screen overflow-hidden bg-neutral-50">
      {/* Sidebar */}
      <div
        className={cn(
          'shrink-0 transition-all duration-300',
          // Mobile: overlay sidebar
          'fixed inset-y-0 left-0 z-30 lg:relative lg:z-auto',
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        <Sidebar />
      </div>

      {/* Mobile overlay backdrop */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={() => useUIStore.getState().setSidebarOpen(false)}
        />
      )}

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          {/* Ranh giới lỗi đặt ở đây (trong Layout) để khi một trang hỏng thì
              sidebar và header vẫn còn, người dùng chuyển trang khác được.
              resetKey theo đường dẫn: rời trang hỏng là ranh giới tự reset. */}
          <ErrorBoundary resetKey={location.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
