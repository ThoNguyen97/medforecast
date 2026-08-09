import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E test configuration for MedForecast AI.
 * Tests run against the Vite dev server at http://localhost:3000.
 */
export default defineConfig({
  testDir: './e2e',
  /* Run tests in each file in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter */
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
  ],
  /* Global timeout per test */
  timeout: 30_000,
  /* Expect timeout */
  expect: {
    timeout: 10_000,
  },

  use: {
    /* Base URL for all tests */
    baseURL: 'http://localhost:3000',
    /* Collect trace on first retry */
    trace: 'on-first-retry',
    /* Take screenshot on failure */
    screenshot: 'only-on-failure',
    /* Action timeout */
    actionTimeout: 10_000,
    /* Navigation timeout */
    navigationTimeout: 15_000,
  },

  projects: [
    /* Desktop browsers */
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    /* Mobile viewport — responsive design testing */
    {
      name: 'mobile-chrome',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 390, height: 844 },
      },
      testMatch: '**/responsive.spec.ts',
    },
    {
      name: 'mobile-safari',
      use: {
        ...devices['iPhone 12'],
      },
      testMatch: '**/responsive.spec.ts',
    },
  ],
});
