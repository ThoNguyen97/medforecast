import { test, expect } from '@playwright/test';
import { loginViaUI } from './helpers/auth';

/**
 * Inventory management flow — E2E tests
 *
 * Covers:
 *  - Inventory page renders with table
 *  - Table has expected columns
 *  - Stock status badges are visible
 *  - Update stock modal can be opened and closed
 *  - Category and Risk Level filters work
 */

test.describe('Inventory Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaUI(page);
    await page.goto('/inventory');
    await expect(page.getByText(/tồn kho vật tư y tế/i)).toBeVisible({
      timeout: 15_000,
    });
  });

  // ------------------------------------------------------------------
  test('page heading and description are visible', async ({ page }) => {
    await expect(page.getByText(/tồn kho vật tư y tế/i)).toBeVisible();
    await expect(
      page.getByText(/quản lý và theo dõi/i)
    ).toBeVisible();
  });

  // ------------------------------------------------------------------
  test('inventory table renders after loading', async ({ page }) => {
    // Wait for loading spinner to disappear
    await expect(page.locator('[class*="LoadingSpinner"], .animate-spin').first()).toBeHidden({
      timeout: 20_000,
    });

    // Table should be visible
    await expect(page.locator('table').first()).toBeVisible({ timeout: 15_000 });
  });

  // ------------------------------------------------------------------
  test('table contains expected column headers', async ({ page }) => {
    await page.waitForSelector('table', { timeout: 20_000 });

    // Check for key column headers (Vietnamese labels)
    const headers = page.locator('thead th, thead td');
    const headerTexts = await headers.allTextContents();
    const combined = headerTexts.join(' ').toLowerCase();

    // At minimum the table should contain supply-related column text
    expect(
      combined.includes('vật tư') ||
      combined.includes('danh mục') ||
      combined.includes('tồn kho') ||
      combined.includes('trạng thái')
    ).toBe(true);
  });

  // ------------------------------------------------------------------
  test('stock status badges are visible in the table', async ({ page }) => {
    await page.waitForSelector('table', { timeout: 20_000 });

    // Stock status badges use badge/pill styled spans
    // They should contain one of: an toàn, thấp, nguy hiểm, critical, low, safe
    const badges = page.locator('table').locator('[class*="badge"], span[class*="bg-"]');
    const count = await badges.count();
    // If there are inventory items there should be at least one badge
    if (count > 0) {
      await expect(badges.first()).toBeVisible();
    }
  });

  // ------------------------------------------------------------------
  test('category filter renders with options', async ({ page }) => {
    // The filter section should contain a select or button group for category
    const categoryFilter = page.locator(
      'select[id*="category"], button:has-text("Tất cả"), [class*="filter"]'
    ).first();
    await expect(categoryFilter).toBeVisible({ timeout: 10_000 });
  });

  // ------------------------------------------------------------------
  test('risk level filter renders with options', async ({ page }) => {
    const riskFilter = page.locator(
      'select[id*="risk"], select[id*="level"], button:has-text("Tất cả")'
    ).first();
    await expect(riskFilter).toBeVisible({ timeout: 10_000 });
  });

  // ------------------------------------------------------------------
  test('update stock modal opens when action button is clicked', async ({ page }) => {
    await page.waitForSelector('table', { timeout: 20_000 });

    // Try clicking the first "Cập nhật" action button in the table
    const updateBtn = page.locator('table').getByRole('button', { name: /cập nhật/i }).first();

    const btnCount = await updateBtn.count();
    if (btnCount === 0) {
      // If no items in table, skip the modal test
      test.skip();
      return;
    }

    await updateBtn.click();

    // Modal should appear
    await expect(
      page.getByRole('dialog').or(page.locator('[class*="Modal"], [class*="modal"]').first())
    ).toBeVisible({ timeout: 10_000 });
  });

  // ------------------------------------------------------------------
  test('update stock modal can be closed', async ({ page }) => {
    await page.waitForSelector('table', { timeout: 20_000 });

    const updateBtn = page.locator('table').getByRole('button', { name: /cập nhật/i }).first();
    const btnCount = await updateBtn.count();
    if (btnCount === 0) {
      test.skip();
      return;
    }

    await updateBtn.click();

    // Close the modal using the cancel button or the X button
    const cancelBtn = page.getByRole('button', { name: /hủy/i }).first();
    if (await cancelBtn.isVisible()) {
      await cancelBtn.click();
    } else {
      // Press Escape to close
      await page.keyboard.press('Escape');
    }

    await expect(
      page.getByRole('dialog').or(page.locator('[class*="Modal"]').first())
    ).toBeHidden({ timeout: 5_000 });
  });

  // ------------------------------------------------------------------
  test('refresh button works without crashing the page', async ({ page }) => {
    const refreshBtn = page.getByRole('button', { name: /làm mới/i });
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();
    // Page heading should remain visible
    await expect(page.getByText(/tồn kho vật tư y tế/i)).toBeVisible();
  });
});
