import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIStore {
  // Sidebar
  isSidebarOpen: boolean;
  isSidebarCollapsed: boolean;

  // Page title
  pageTitle: string;

  // Loading states
  isGlobalLoading: boolean;

  // Notifications
  unreadNotificationsCount: number;

  // Actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebarCollapsed: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setPageTitle: (title: string) => void;
  setGlobalLoading: (loading: boolean) => void;
  setUnreadNotificationsCount: (count: number) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      isSidebarOpen: true,
      isSidebarCollapsed: false,
      pageTitle: 'Dashboard',
      isGlobalLoading: false,
      unreadNotificationsCount: 0,

      toggleSidebar: () =>
        set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),

      setSidebarOpen: (open) =>
        set({ isSidebarOpen: open }),

      toggleSidebarCollapsed: () =>
        set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),

      setSidebarCollapsed: (collapsed) =>
        set({ isSidebarCollapsed: collapsed }),

      setPageTitle: (title) =>
        set({ pageTitle: title }),

      setGlobalLoading: (loading) =>
        set({ isGlobalLoading: loading }),

      setUnreadNotificationsCount: (count) =>
        set({ unreadNotificationsCount: count }),
    }),
    {
      name: 'medforecast-ui',
      partialize: (state) => ({
        isSidebarCollapsed: state.isSidebarCollapsed,
      }),
    }
  )
);
