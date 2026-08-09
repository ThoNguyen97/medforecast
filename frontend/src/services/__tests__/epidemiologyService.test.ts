import { describe, it, expect, vi, beforeEach } from 'vitest';
import { epidemiologyService } from '../epidemiologyService';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe('epidemiologyService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getDiseaseCases calls GET /disease-cases', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    await epidemiologyService.getDiseaseCases();
    expect(api.get).toHaveBeenCalledWith('/disease-cases', { params: undefined });
  });

  it('getDiseaseCases passes disease_type param', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    await epidemiologyService.getDiseaseCases({ disease_type: 'dengue_fever' });
    expect(api.get).toHaveBeenCalledWith('/disease-cases', {
      params: { disease_type: 'dengue_fever' },
    });
  });

  it('createDiseaseCase calls POST /disease-cases', async () => {
    const newCase = { disease_type: 'dengue_fever', case_count: 10, location: 'HCM', recorded_at: '2024-01-01T00:00:00' };
    vi.mocked(api.post).mockResolvedValueOnce({ data: { id: 1, ...newCase } });
    const result = await epidemiologyService.createDiseaseCase(newCase as any);
    expect(api.post).toHaveBeenCalledWith('/disease-cases', newCase);
    expect(result).toHaveProperty('id', 1);
  });

  it('getStatistics calls GET /disease-cases/stats', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {} });
    await epidemiologyService.getStatistics({ location: 'HCM' });
    expect(api.get).toHaveBeenCalledWith('/disease-cases/stats', {
      params: { location: 'HCM' },
    });
  });

  it('getTrends calls GET /disease-cases/trends', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: {} });
    await epidemiologyService.getTrends({ disease_type: 'seasonal_flu', limit: 30 });
    expect(api.get).toHaveBeenCalledWith('/disease-cases/trends', {
      params: { disease_type: 'seasonal_flu', limit: 30 },
    });
  });
});
