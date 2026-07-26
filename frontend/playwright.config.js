import { defineConfig } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';

// Shared temporary directory used by all E2E tests.
// The DATA_DIR and CONFIG_PATH env vars are injected into the backend
// process so tests never touch real application data.
const E2E_TMP = path.join(os.tmpdir(), 'cpo-e2e-test');
const E2E_CONFIG_PATH = path.join(E2E_TMP, 'config.json');
const E2E_DATA_DIR = path.join(E2E_TMP, 'data');

// Override with E2E_PORT when 8002 is taken (e.g. by a running dev container).
const E2E_PORT = process.env.E2E_PORT ?? '8002';

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: `http://localhost:${E2E_PORT}`,
    headless: true,
  },
  webServer: {
    command: `cd ../backend && uvicorn main:app --port ${E2E_PORT}`,
    url: `http://localhost:${E2E_PORT}`,
    reuseExistingServer: !process.env.CI,
    env: {
      CONFIG_PATH: E2E_CONFIG_PATH,
      DATA_DIR: E2E_DATA_DIR,
      // Every e2e login comes from 127.0.0.1; the human-scale default of 5
      // per minute would throttle the suite after a couple of tests.
      LOGIN_MAX_ATTEMPTS: '1000',
    },
  },
});
