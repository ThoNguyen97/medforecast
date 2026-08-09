import { describe, it, expect, beforeEach } from 'vitest';
import { useUIStore } from '../uiStore';

describe('uiStore', () => {
  beforeEach(() => {
    useUIStore.setState({
      isSidebarOpen: true,
      isSidebarCollapsed: false,
      pageTitle: 'Dashboard',
      isGlobalLoading: false,
      unreadNotificationsCount: 0,
    });
  });

  it('has default sidebar open', () => {
    expect(useUIStore.getState().isSidebarOpen).toBe(true);
  });

  it('toggleSidebar flips isSidebarOpen', () => {
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().isSidebarOpen).toBe(false);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().isSidebarOpen).toBe(true);
  });

  it('setSidebarOpen sets value', () => {
    useUIStore.getState().setSidebarOpen(false);
    expect(useUIStore.getState().isSidebarOpen).toBe(false);
  });

  it('toggleSidebarCollapsed flips isSidebarCollapsed', () => {
    expect(useUIStore.getState().isSidebarCollapsed).toBe(false);
    useUIStore.getState().toggleSidebarCollapsed();
    expect(useUIStore.getState().isSidebarCollapsed).toBe(true);
  });

  it('setSidebarCollapsed sets value', () => {
    useUIStore.getState().setSidebarCollapsed(true);
    expect(useUIStore.getState().isSidebarCollapsed).toBe(true);
  });

  it('setPageTitle updates title', () => {
    useUIStore.getState().setPageTitle('Inventory');
    expect(useUIStore.getState().pageTitle).toBe('Inventory');
  });

  it('setGlobalLoading updates loading state', () => {
    useUIStore.getState().setGlobalLoading(true);
    expect(useUIStore.getState().isGlobalLoading).toBe(true);
  });

  it('setUnreadNotificationsCount updates count', () => {
    useUIStore.getState().setUnreadNotificationsCount(5);
    expect(useUIStore.getState().unreadNotificationsCount).toBe(5);
  });
});
