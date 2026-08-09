import type { Page } from '@playwright/test';

/** Default seed credentials created by the backend seed script. */
export const ADMIN_CREDENTIALS = {
  username: 'admin',
  password: 'admin123',
} as const;

/**
 * Log in via the login page UI and wait until the dashboard is visible.
 *
 * @param page - Playwright Page object
 * @param credentials - Username / password pair (defaults to admin seed user)
 */
export async function loginViaUI(
  page: Page,
  credentials: { username: string; password: string } = ADMIN_CREDENTIALS
): Promise<void> {
  await page.goto('/login');

  await page.getByLabel('Tên đăng nhập').fill(credentials.username);
  await page.getByLabel('Mật khẩu').fill(credentials.password);
  await page.getByRole('button', { name: 'Đăng nhập' }).click();

  // Wait until navigation leaves the login page (redirect to dashboard)
  await page.waitForURL((url) => !url.pathname.includes('/login'), {
    timeout: 15_000,
  });
}

/**
 * Log out the current user by navigating to the sidebar logout button.
 */
export async function logoutViaUI(page: Page): Promise<void> {
  // The sidebar Header contains a user menu / logout button
  const logoutBtn = page.getByRole('button', { name: /đăng xuất/i });
  if (await logoutBtn.isVisible()) {
    await logoutBtn.click();
  }
  // Fallback: clear localStorage and reload to the login page
  await page.evaluate(() => {
    localStorage.clear();
  });
  await page.goto('/login');
}
