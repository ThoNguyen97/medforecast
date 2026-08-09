import { describe, it, expect } from 'vitest';
import {
  TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  USER_KEY,
  TOKEN_EXPIRY_KEY,
  SESSION_TIMEOUT_MINUTES,
  DASHBOARD_REFRESH_INTERVAL_MS,
  DISEASE_TYPE_LABELS,
  SUPPLY_CATEGORY_LABELS,
  ALERT_SEVERITY_LABELS,
  ALERT_SEVERITY_COLORS,
  STOCK_STATUS_LABELS,
  USER_ROLE_LABELS,
  FORECAST_PERIOD_OPTIONS,
  ROUTES,
  APP_NAME,
} from '../constants';

describe('constants', () => {
  it('defines storage keys', () => {
    expect(TOKEN_KEY).toBe('medforecast_token');
    expect(REFRESH_TOKEN_KEY).toBe('medforecast_refresh_token');
    expect(USER_KEY).toBe('medforecast_user');
    expect(TOKEN_EXPIRY_KEY).toBe('medforecast_token_expiry');
  });

  it('sets session timeout to 30 minutes', () => {
    expect(SESSION_TIMEOUT_MINUTES).toBe(30);
  });

  it('sets dashboard refresh interval to 5 minutes in ms', () => {
    expect(DASHBOARD_REFRESH_INTERVAL_MS).toBe(5 * 60 * 1000);
  });

  it('defines disease type labels', () => {
    expect(DISEASE_TYPE_LABELS.dengue_fever).toBeTruthy();
    expect(DISEASE_TYPE_LABELS.seasonal_flu).toBeTruthy();
    expect(DISEASE_TYPE_LABELS.respiratory_disease).toBeTruthy();
  });

  it('defines supply category labels', () => {
    expect(SUPPLY_CATEGORY_LABELS.mask).toBeTruthy();
    expect(SUPPLY_CATEGORY_LABELS.glove).toBeTruthy();
  });

  it('defines all alert severity labels', () => {
    expect(ALERT_SEVERITY_LABELS.critical).toBeTruthy();
    expect(ALERT_SEVERITY_LABELS.high).toBeTruthy();
    expect(ALERT_SEVERITY_LABELS.medium).toBeTruthy();
  });

  it('defines alert severity colors', () => {
    expect(ALERT_SEVERITY_COLORS.critical).toBe('danger');
    expect(ALERT_SEVERITY_COLORS.high).toBe('warning');
  });

  it('defines stock status labels', () => {
    expect(STOCK_STATUS_LABELS.safe).toBeTruthy();
    expect(STOCK_STATUS_LABELS.low).toBeTruthy();
    expect(STOCK_STATUS_LABELS.critical).toBeTruthy();
  });

  it('defines user role labels', () => {
    expect(USER_ROLE_LABELS.Administrator).toBeTruthy();
    expect(USER_ROLE_LABELS.Pharmacist).toBeTruthy();
    expect(USER_ROLE_LABELS.Inventory_Manager).toBeTruthy();
  });

  it('defines forecast period options as 7, 14, 30 days', () => {
    const values = FORECAST_PERIOD_OPTIONS.map((o) => o.value);
    expect(values).toContain(7);
    expect(values).toContain(14);
    expect(values).toContain(30);
  });

  it('defines route paths', () => {
    expect(ROUTES.LOGIN).toBe('/login');
    expect(ROUTES.DASHBOARD).toBe('/dashboard');
    expect(ROUTES.INVENTORY).toBe('/inventory');
  });

  it('defines app name', () => {
    expect(APP_NAME).toBe('MedForecast AI');
  });
});
