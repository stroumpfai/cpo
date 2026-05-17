/**
 * Shared E2E test fixtures for the CPO application.
 *
 * Seeding strategy:
 * - seedAdmin copies config/test-config.json to the data directory so that a
 *   known admin account (username: "david", password matching the bcrypt hash
 *   in test-config.json) is available.  The test-config.json already contains
 *   a bcrypt hash; we avoid re-hashing in JS by reusing that file directly.
 *
 * - All other fixtures talk to the live backend API, which is already running
 *   when Playwright executes (started via webServer in playwright.config.js).
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Path to the pre-seeded config file checked into the repo.
const TEST_CONFIG_PATH = path.resolve(__dirname, '../../config/test-config.json');

// ---------------------------------------------------------------------------
// seedAdmin
// ---------------------------------------------------------------------------

/**
 * Copies config/test-config.json to `dataDir/config.json`.
 *
 * The test-config.json contains:
 *   admin: { username: "david", password_hash: "<bcrypt hash>" }
 *   cpos:  []
 *
 * After calling this, you can log in as the admin via the API or UI with the
 * credentials stored in TEST_ADMIN below.
 *
 * @param {string} dataDir - Absolute path to the directory where config.json
 *   should be written (e.g. the Docker volume or local /app/config equivalent).
 */
export function seedAdmin(dataDir) {
  fs.mkdirSync(dataDir, { recursive: true });
  const dest = path.join(dataDir, 'config.json');
  fs.copyFileSync(TEST_CONFIG_PATH, dest);
}

// Known credentials that match the hash stored in test-config.json.
export const TEST_ADMIN = {
  username: 'david',
  password: 'AdminPass123!',
};

// ---------------------------------------------------------------------------
// seedCpo
// ---------------------------------------------------------------------------

/**
 * Creates a CPO account via the admin API.
 *
 * @param {string} baseURL - e.g. "http://localhost:8002"
 * @param {string} adminToken - JWT returned by loginAs for the admin account
 * @param {{ username: string, password: string, email: string, team_name?: string }} opts
 * @returns {Promise<object>} The CPOResponse JSON from the API
 */
export async function seedCpo(baseURL, adminToken, { username, password, email, team_name }) {
  const res = await fetch(`${baseURL}/api/admin/cpos`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${adminToken}`,
    },
    body: JSON.stringify({
      username,
      email,
      team_name: team_name ?? `${username}'s Team`,
      initial_password: password,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`seedCpo failed (${res.status}): ${text}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// seedMenu
// ---------------------------------------------------------------------------

/**
 * Adds pizzas to the CPO's menu via the API.
 *
 * @param {string} baseURL
 * @param {string} cpoToken - JWT returned after logging in as CPO
 * @param {Array<{ name: string, price: number }>} pizzas
 * @returns {Promise<object[]>} Array of PizzaResponse objects
 */
export async function seedMenu(baseURL, cpoToken, pizzas) {
  const results = [];

  for (const pizza of pizzas) {
    const res = await fetch(`${baseURL}/api/cpo/menu`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${cpoToken}`,
      },
      body: JSON.stringify({ name: pizza.name, price: pizza.price }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`seedMenu failed for "${pizza.name}" (${res.status}): ${text}`);
    }

    results.push(await res.json());
  }

  return results;
}

// ---------------------------------------------------------------------------
// seedSession
// ---------------------------------------------------------------------------

/**
 * Creates a session via the CPO API.
 *
 * @param {string} baseURL
 * @param {string} cpoToken
 * @param {{ date: string, startTime: string, endTime: string, gracePeriodMinutes?: number }} opts
 *   date format: "YYYY-MM-DD", time format: "HH:MM"
 * @returns {Promise<object>} SessionResponse JSON
 */
export async function seedSession(baseURL, cpoToken, { date, startTime, endTime, gracePeriodMinutes = 2 }) {
  const res = await fetch(`${baseURL}/api/cpo/sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${cpoToken}`,
    },
    body: JSON.stringify({
      session_date: date,
      start_time: startTime,
      end_time: endTime,
      grace_period_minutes: gracePeriodMinutes,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`seedSession failed (${res.status}): ${text}`);
  }

  return res.json();
}

// ---------------------------------------------------------------------------
// loginAs
// ---------------------------------------------------------------------------

/**
 * Logs in via the browser UI and returns the JWT token stored in localStorage.
 *
 * Uses the actual form fields from LoginPage.jsx:
 *   <input id="username" ...>
 *   <input id="password" ...>
 *   <button type="submit" ...>
 *
 * After submit, waits for navigation away from /login before returning.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} baseURL
 * @param {string} username
 * @param {string} password
 * @returns {Promise<string>} The JWT token from localStorage
 */
export async function loginAs(page, baseURL, username, password) {
  await page.goto(`${baseURL}/login`);
  await page.fill('#username', username);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  // Wait until we've left the login page
  await page.waitForURL((url) => !url.pathname.endsWith('/login'));
  // Retrieve the token stored by the React app
  const token = await page.evaluate(() => localStorage.getItem('token'));
  return token;
}

// ---------------------------------------------------------------------------
// apiLogin  (helper for seeding without a browser)
// ---------------------------------------------------------------------------

/**
 * Calls the login API directly (no browser) and returns the JWT token.
 * Useful for obtaining tokens during setup steps before the browser is needed.
 *
 * @param {string} baseURL
 * @param {string} username
 * @param {string} password
 * @returns {Promise<string>} JWT token
 */
export async function apiLogin(baseURL, username, password) {
  const res = await fetch(`${baseURL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`apiLogin failed for "${username}" (${res.status}): ${text}`);
  }

  const data = await res.json();
  return data.token;
}
