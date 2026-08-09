import { describe, it, expect, vi, beforeEach } from 'vitest';
import { configService } from '../configService';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));

describe('configService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getConfigs calls GET /config', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    const result = await configService.getConfigs();
    expect(api.get).toHaveBeenCalledWith('/config');
    expect(result).toEqual([]);
  });

  it('getConfigByKey calls GET /config/:key', async () => {
    const cfg = { config_key: 'alert_threshold', config_value: '100' };
    vi.mocked(api.get).mockResolvedValueOnce({ data: cfg });
    const result = await configService.getConfigByKey('alert_threshold');
    expect(api.get).toHaveBeenCalledWith('/config/alert_threshold');
    expect(result).toEqual(cfg);
  });

  it('updateConfig calls PUT /config/:key', async () => {
    vi.mocked(api.put).mockResolvedValueOnce({ data: {} });
    await configService.updateConfig('alert_threshold', { config_value: '200' });
    expect(api.put).toHaveBeenCalledWith('/config/alert_threshold', { config_value: '200' });
  });

  it('getConversionRatios calls GET /config/conversion-ratios', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    await configService.getConversionRatios();
    expect(api.get).toHaveBeenCalledWith('/config/conversion-ratios');
  });

  it('updateConversionRatios calls PUT /config/conversion-ratios', async () => {
    vi.mocked(api.put).mockResolvedValueOnce({ data: [] });
    await configService.updateConversionRatios({ ratios: [] } as any);
    expect(api.put).toHaveBeenCalledWith('/config/conversion-ratios', { ratios: [] });
  });

  it('getThresholds calls GET /config/thresholds', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    await configService.getThresholds();
    expect(api.get).toHaveBeenCalledWith('/config/thresholds');
  });

  it('updateThresholds calls PUT /config/thresholds', async () => {
    vi.mocked(api.put).mockResolvedValueOnce({ data: [] });
    await configService.updateThresholds({ thresholds: [] } as any);
    expect(api.put).toHaveBeenCalledWith('/config/thresholds', { thresholds: [] });
  });

  it('getAuditLogs calls GET /audit-logs', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [] });
    await configService.getAuditLogs({ limit: 50 });
    expect(api.get).toHaveBeenCalledWith('/audit-logs', { params: { limit: 50 } });
  });
});
