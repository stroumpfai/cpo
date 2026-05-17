import { defineConfig } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';

// Shared temporary directory used by all E2E tests.
// The DATA_DIR and CONFIG_PATH env vars are injected into the backend
// process so tests never touch real application data.
const E2E_TMP = path.join(os.tmpdir(), 'cpo-e2e-test');
const E2E_CONFIG_PATH = path.join(E2E_TMP, 'config.json');
const E2E_DATA_DIR = path.join(E2E_TMP, 'data');

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:8002',
    headless: true,
  },
  webServer: {
    command: 'cd ../backend && uvicorn main:app --port 8002',
    url: 'http://localhost:8002',
    reuseExistingServer: !process.env.CI,
    env: {
      CONFIG_PATH: E2E_CONFIG_PATH,
      DATA_DIR: E2E_DATA_DIR,
    },
  },
});
