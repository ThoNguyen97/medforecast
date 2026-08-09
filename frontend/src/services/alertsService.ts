import api from './api';
import type { Alert } from '../types/alerts';

export const alertsService = {
  /**
   * Get all alerts with optional filters
   */
  async getAlerts(params?: {
    skip?: number;
    limit?: number;
    severity?: string;
    is_resolved?: boolean;
  }): Promise<Alert[]> {
    const response = await api.get<Alert[]>('/alerts', { params });
    return response.data;
  },

  /**
   * Get active (unresolved) alerts only
   */
  async getActiveAlerts(params?: {
    skip?: number;
    limit?: number;
  }): Promise<Alert[]> {
    const response = await api.get<Alert[]>('/alerts/active', { params });
    return response.data;
  },

  /**
   * Get a single alert by ID
   */
  async getAlertById(id: number): Promise<Alert> {
    const response = await api.get<Alert>(`/alerts/${id}`);
    return response.data;
  },

  /**
   * Resolve an alert by marking it as resolved
   */
  async resolveAlert(id: number): Promise<Alert> {
    const response = await api.put<Alert>(`/alerts/${id}/resolve`);
    return response.data;
  },

  /**
   * Fulfill an alert: add the shortage quantity to inventory and resolve.
   */
  async fulfillAlert(id: number): Promise<Alert> {
    const response = await api.post<Alert>(`/alerts/${id}/fulfill`);
    return response.data;
  },

  /**
   * Get critical alerts only
   */
  async getCriticalAlerts(params?: {
    skip?: number;
    limit?: number;
  }): Promise<Alert[]> {
    const response = await api.get<Alert[]>('/alerts/critical', { params });
    return response.data;
  },
};
