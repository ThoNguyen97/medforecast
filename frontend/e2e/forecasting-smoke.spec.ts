import { test, expect } from '@playwright/test';
import { loginViaUI } from './helpers/auth';

/**
 * Smoke test: log in, open Phân tích & Dự báo, run analyze and screenshot.
 * Mục tiêu: tự verify flow click nút "Phân tích" hoạt động end-to-end.
 */
test('forecasting page renders chart after click Phân tích', async ({ page }) => {
  await loginViaUI(page);
  await page.goto('/forecasting');

  // Đảm bảo title hiển thị
  await expect(page.getByRole('heading', { name: 'Dự báo số ca bệnh' })).toBeVisible();

  // Chọn tháng 6/2026 (form date input dùng kiểu YYYY-MM)
  const monthInput = page.locator('input[type="month"]');
  await monthInput.fill('2026-06');

  // Bắt request analyze
  const analyzeReq = page.waitForResponse(
    (resp) => resp.url().includes('/forecast/analyze') && resp.status() === 200,
    { timeout: 15_000 },
  );

  await page.getByRole('button', { name: 'Phân tích', exact: true }).click();
  await analyzeReq;

  // Kiểm tra UI sau khi có result
  await expect(page.getByText(/Dự báo \(tháng 06\/2026\)/i)).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText('Giải thích mô hình')).toBeVisible();
  await expect(page.getByText('Biểu đồ dự báo so với thực tế')).toBeVisible();

  await page.screenshot({ path: 'e2e/__screenshots__/forecasting-result.png', fullPage: true });
});
