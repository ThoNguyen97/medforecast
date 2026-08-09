import { describe, it, expect, vi, beforeEach } from 'vitest';
import { reportsService } from '../reportsService';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('reportsService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getConsumptionReport calls GET /reports/consumption', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {} });
    await reportsService.getConsumptionReport({ start_date: '2024-01-01', end_date: '2024-01-31' });
    expect(api.get).toHaveBeenCalledWith('/reports/consumption', expect.objectContaining({
      params: expect.objectContaining({ start_date: '2024-01-01' }),
    }));
  });

  it('getConsumptionReport passes undefined for empty filters', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {} });
    await reportsService.getConsumptionReport();
    expect(api.get).toHaveBeenCalledWith('/reports/consumption', expect.any(Object));
  });

  it('getForecastAccuracyReport calls GET /reports/forecast-accuracy', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {} });
    await reportsService.getForecastAccuracyReport();
    expect(api.get).toHaveBeenCalledWith('/reports/forecast-accuracy', expect.any(Object));
  });

  it('getInventoryTurnoverReport calls GET /reports/inventory-turnover', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {} });
    await reportsService.getInventoryTurnoverReport();
    expect(api.get).toHaveBeenCalledWith('/reports/inventory-turnover', expect.any(Object));
  });

  it('exportReport calls POST /reports/export with blob', async () => {
    const mockBlob = new Blob(['data'], { type: 'application/pdf' });
    vi.mocked(api.post).mockResolvedValueOnce({ data: mockBlob });
    const result = await reportsService.exportReport({ report_type: 'consumption' } as any);
    expect(api.post).toHaveBeenCalledWith('/reports/export', { report_type: 'consumption' }, { responseType: 'blob' });
    expect(result).toBeInstanceOf(Blob);
  });
});
