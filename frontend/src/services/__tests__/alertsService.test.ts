import { describe, it, expect, vi, beforeEach } from 'vitest';
import { alertsService } from '../alertsService';
import api from '../api';
import type { Alert } from '../../types/alerts';

vi.mock('../api', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const mockAlert: Alert = {
  id: 1,
  supply_id: 10,
  supply_name: 'Khẩu trang',
  alert_type: 'low_stock',
  severity: 'critical',
  message: 'Low stock',
  shortage_date: '2024-02-01',
  current_stock: 50,
  required_stock: 250,
  is_resolved: false,
  created_at: '2024-01-01T00:00:00',
};

describe('alertsService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getAlerts', () => {
    it('calls GET /alerts', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [mockAlert] });
      const result = await alertsService.getAlerts();
      expect(api.get).toHaveBeenCalledWith('/alerts', { params: undefined });
      expect(result).toEqual([mockAlert]);
    });

    it('passes severity filter', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
      await alertsService.getAlerts({ severity: 'critical' });
      expect(api.get).toHaveBeenCalledWith('/alerts', { params: { severity: 'critical' } });
    });
  });

  describe('getActiveAlerts', () => {
    it('calls GET /alerts/active', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
      await alertsService.getActiveAlerts();
      expect(api.get).toHaveBeenCalledWith('/alerts/active', { params: undefined });
    });
  });

  describe('getAlertById', () => {
    it('calls GET /alerts/:id', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockAlert });
      const result = await alertsService.getAlertById(1);
      expect(api.get).toHaveBeenCalledWith('/alerts/1');
      expect(result).toEqual(mockAlert);
    });
  });

  describe('resolveAlert', () => {
    it('calls PUT /alerts/:id/resolve', async () => {
      const resolved = { ...mockAlert, is_resolved: true };
      vi.mocked(api.put).mockResolvedValueOnce({ data: resolved });
      const result = await alertsService.resolveAlert(1);
      expect(api.put).toHaveBeenCalledWith('/alerts/1/resolve');
      expect(result.is_resolved).toBe(true);
    });
  });

  describe('getCriticalAlerts', () => {
    it('calls GET /alerts/critical', async () => {
      vi.mocked(api.get).mockResolvedValueOnce({ data: [mockAlert] });
      await alertsService.getCriticalAlerts();
      expect(api.get).toHaveBeenCalledWith('/alerts/critical', { params: undefined });
    });
  });
});
