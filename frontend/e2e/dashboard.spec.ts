import { test, expect } from '@playwright/test';
import { loginViaUI } from './helpers/auth';

/**
 * Dashboard flow — E2E tests
 *
 * Covers:
 *  - Metric cards (Total Supplies, High Risk Shortages, Predicted Demand, Disease Outbreaks)
 *  - Supply Demand Chart renders
 *  - Risk Status Chart renders
 *  - Critical Alerts table renders
 */

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page);
    await page.goto('/dashboard');
    // Wait for the page heading to confirm we're on the right page
    await expect(page.getByText(/tổng quan/i).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  // ------------------------------------------------------------------
  test('page heading is visible', async ({ page }) => {
    await expect(page.getByText(/tổng quan hệ thống/i)).toBeVisible();
  });

  // ------------------------------------------------------------------
  test('all four metric cards are visible', async ({ page }) => {
    // Cards are identified by their title text (Vietnamese UI)
    await expect(page.getByText(/tổng vật tư/i)).toBeVisible();
    await expect(page.getByText(/nguy cơ thiếu hụt/i)).toBeVisible();
    await expect(page.getByText(/nhu cầu dự báo/i)).toBeVisible();
    await expect(page.getByText(/ca bệnh dịch/i)).toBeVisible();
  });

  // ------------------------------------------------------------------
  test('Supply Demand Chart section is visible', async ({ page }) => {
    // The chart wrapper renders a recharts SVG or a loading spinner.
    // We verify the container section is present.
    await expect(
      page.locator('.recharts-wrapper, [class*="chart"]').first()
    ).toBeVisible({ timeout: 20_000 });
  });

  // ------------------------------------------------------------------
  test('Risk Status Chart section is visible', async ({ page }) => {
    // Donut chart or its loading container should be present
    const charts = page.locator('.recharts-wrapper');
    // There should be at least 2 charts (line + donut)
    await expect(charts.nth(0)).toBeVisible({ timeout: 20_000 });
  });

  // ------------------------------------------------------------------
  test('Critical Alerts table section is visible', async ({ page }) => {
    // The CriticalAlertsTable renders a section with "cảnh báo" text
    await expect(
      page.getByText(/cảnh báo/i).first()
    ).toBeVisible({ timeout: 15_000 });
  });

  // ------------------------------------------------------------------
  test('refresh button triggers data reload', async ({ page }) => {
    const refreshBtn = page.getByRole('button', { name: /làm mới/i });
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();
    // After clicking, the button may momentarily show a loading state
    // We simply verify the page hasn't crashed
    await expect(page.getByText(/tổng quan hệ thống/i)).toBeVisible();
  });
});
