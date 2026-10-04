import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/browser',
  timeout: 20000,
  expect: { timeout: 5000 },
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure' },
  webServer: {
    command: process.env.TEST_PRODUCTION ? 'corepack pnpm start' : 'corepack pnpm dev --port 4173 --strictPort',
    env: { BACKEND_URL: 'http://127.0.0.1:4187', HOST: '127.0.0.1', PORT: '4173', ORIGIN: 'http://127.0.0.1:4173' },
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 30000
  }
});
