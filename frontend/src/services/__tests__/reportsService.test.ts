import { describe, it, expect, vi, beforeEach } from 'vitest';
import { reportsService } from '../reportsService';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('reportsService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getForecastAccuracyReport gọi GET /reports/forecast-accuracy', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {} });
    await reportsService.getForecastAccuracyReport({ start_date: '2026-01-01' });
    expect(api.get).toHaveBeenCalledWith('/reports/forecast-accuracy', expect.objectContaining({
      params: expect.objectContaining({ start_date: '2026-01-01' }),
    }));
  });

  it('exportReport gọi POST /reports/export và trả Blob', async () => {
    const mockBlob = new Blob(['data'], { type: 'application/pdf' });
    vi.mocked(api.post).mockResolvedValueOnce({ data: mockBlob });
    const result = await reportsService.exportReport({ report_type: 'dashboard-summary', format: 'pdf' });
    expect(api.post).toHaveBeenCalledWith(
      '/reports/export',
      { report_type: 'dashboard-summary', format: 'pdf' },
      { responseType: 'blob' },
    );
    expect(result).toBeInstanceOf(Blob);
  });
});
