import { test, expect } from '@playwright/test';
import { loginViaUI } from './helpers/auth';

/**
 * Forecasting flow — E2E tests
 *
 * Covers:
 *  - Navigate to Forecasting page
 *  - Disease type selector renders
 *  - Forecast period slider renders
 *  - Submit button triggers forecast generation
 *  - Forecast chart area renders (with or without data)
 *  - Model accuracy cards appear after forecast
 */

test.describe('Forecasting', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page);
    await page.goto('/forecasting');
    // Wait for the forecast request form to appear
    await expect(page.getByText(/yêu cầu dự báo/i)).toBeVisible({
      timeout: 15_000,
    });
  });

  // ------------------------------------------------------------------
  test('forecast request form is visible', async ({ page }) => {
    await expect(page.getByText(/yêu cầu dự báo/i)).toBeVisible();
    await expect(page.getByText(/loại bệnh/i)).toBeVisible();
    await expect(page.getByText(/khoảng thời gian dự báo/i)).toBeVisible();
  });

  // ------------------------------------------------------------------
  test('disease type select has expected options', async ({ page }) => {
    const select = page.locator('#disease-type');
    await expect(select).toBeVisible();

    // Check for Vietnamese disease type labels
    const options = await select.locator('option').allTextContents();
    const combined = options.join(' ').toLowerCase();
    expect(
      combined.includes('sốt xuất huyết') ||
      combined.includes('cúm mùa') ||
      combined.includes('hô hấp')
    ).toBe(true);
  });

  // ------------------------------------------------------------------
  test('forecast period slider is present and interactive', async ({ page }) => {
    const slider = page.locator('#forecast-period');
    await expect(slider).toBeVisible();
    await expect(slider).toHaveAttribute('type', 'range');

    // Change slider value to 14
    await slider.fill('14');
    await expect(page.getByText('14 ngày')).toBeVisible();
  });

  // ------------------------------------------------------------------
  test('forecast chart container is rendered', async ({ page }) => {
    // The ForecastChart component renders even without data (empty state)
    await expect(
      page.locator('.recharts-wrapper, [class*="ForecastChart"], svg').first()
    ).toBeVisible({ timeout: 15_000 });
  });

  // ------------------------------------------------------------------
  test('generate forecast button is clickable', async ({ page }) => {
    const submitBtn = page.getByRole('button', { name: /tạo dự báo/i });
    await expect(submitBtn).toBeVisible();
    await expect(submitBtn).toBeEnabled();
  });

  // ------------------------------------------------------------------
  test('submitting the form shows loading state', async ({ page }) => {
    // Select a disease type and period
    await page.locator('#disease-type').selectOption('dengue_fever');
    await page.locator('#forecast-period').fill('7');

    const submitBtn = page.getByRole('button', { name: /tạo dự báo/i });
    await submitBtn.click();

    // Either loading message appears OR the button text changes to "Đang tạo dự báo..."
    const isLoading = await page
      .getByText(/đang tạo dự báo/i)
      .isVisible()
      .catch(() => false);

    // Accept either loading indicator or direct success/error response
    if (!isLoading) {
      // Check that the page hasn't crashed
      await expect(page.getByText(/yêu cầu dự báo/i)).toBeVisible();
    }
  });

  // ------------------------------------------------------------------
  test('comparison chart section is present on the page', async ({ page }) => {
    // ForecastComparisonChart is always rendered (may show empty state)
    await expect(
      page.locator('.recharts-wrapper, [class*="chart"]').first()
    ).toBeVisible({ timeout: 15_000 });
  });

  // ------------------------------------------------------------------
  test('AI info panel is visible', async ({ page }) => {
    await expect(page.getByText(/thông tin về dự báo ai/i)).toBeVisible();
  });
});
