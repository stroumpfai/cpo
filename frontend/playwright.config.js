import { defineConfig } from '@playwright/test';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Shared temporary directory used by all E2E tests.
// The DATA_DIR and CONFIG_PATH env vars are injected into the backend
// process so tests never touch real application data.
const E2E_TMP = path.join(os.tmpdir(), 'cpo-e2e-test');
const E2E_CONFIG_PATH = path.join(E2E_TMP, 'config.json');
const E2E_DATA_DIR = path.join(E2E_TMP, 'data');

// Override with E2E_PORT when 8002 is taken (e.g. by a running dev container).
// The suite always starts its own backend (see reuseExistingServer below), so a
// busy port is a hard error rather than a silent hijack — pick a free one.
const E2E_PORT = process.env.E2E_PORT ?? '8002';

// The backend's dependencies live in the repo's venv, not in the system
// Python, so prefer its interpreter when it is there.
const VENV_PYTHON = path.resolve(__dirname, '../venv/bin/python');
const SERVER_CMD = fs.existsSync(VENV_PYTHON)
  ? `cd ../backend && ${VENV_PYTHON} -m uvicorn main:app --port ${E2E_PORT}`
  : `cd ../backend && uvicorn main:app --port ${E2E_PORT}`;

export default defineConfig({
  testDir: './e2e',
  // Every spec resets the *same* backend database in beforeEach, and the order
  // rate limit is keyed on the client IP — which is 127.0.0.1 for all of them.
  // Two spec files running concurrently would therefore wipe each other's
  // fixtures and trip each other's rate limit, so the suite runs serially.
  workers: 1,
  use: {
    baseURL: `http://localhost:${E2E_PORT}`,
    headless: true,
  },
  webServer: {
    command: SERVER_CMD,
    url: `http://localhost:${E2E_PORT}`,
    // Never reuse. Reusing whatever answers on the port sounds like a
    // convenience, but the CONFIG_PATH/DATA_DIR below only apply to a server
    // Playwright starts itself: against a reused one the fixtures would seed
    // teams, menus and orders straight into that instance's real database —
    // and would be exercising its bundle, not the working tree. Starting our
    // own costs a few seconds and makes a busy port fail loudly instead.
    reuseExistingServer: false,
    env: {
      CONFIG_PATH: E2E_CONFIG_PATH,
      DATA_DIR: E2E_DATA_DIR,
      // The backend refuses to boot without a signing secret. Tests never
      // outlive the server they started, so a throwaway secret is enough —
      // an exported JWT_SECRET still wins (e.g. when reusing a dev server).
      JWT_SECRET: process.env.JWT_SECRET ?? crypto.randomBytes(32).toString('hex'),
      // Every e2e login comes from 127.0.0.1; the human-scale default of 5
      // per minute would throttle the suite after a couple of tests.
      LOGIN_MAX_ATTEMPTS: '1000',
    },
  },
});
