/**
 * Shared E2E test fixtures for the CPO application.
 *
 * Seeding strategy:
 * - resetDatabase wipes all rows in the backend's SQLite database (which the
 *   already-running server keeps using) and inserts a known admin account
 *   (username: "david", bcrypt hash reused from config/test-config.json so we
 *   never re-hash in JS). Storage moved from JSON files to SQLite, so per-test
 *   resets must edit the database directly — the legacy config.json is only
 *   imported once at first startup.
 *
 * - All other fixtures talk to the live backend API, which is already running
 *   when Playwright executes (started via webServer in playwright.config.js).
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Path to the pre-seeded config file checked into the repo.
const TEST_CONFIG_PATH = path.resolve(__dirname, '../../config/test-config.json');

// ---------------------------------------------------------------------------
// resetDatabase
// ---------------------------------------------------------------------------

/**
 * Empties every table of the backend's SQLite database and seeds the known
 * admin account from config/test-config.json. Safe to call between tests
 * while the server is running (same file, WAL mode).
 *
 * @param {string} dataDir - The backend's DATA_DIR (contains cpo.db).
 */
export function resetDatabase(dataDir) {
  const dbPath = path.join(dataDir, 'cpo.db');
  const { admin } = JSON.parse(fs.readFileSync(TEST_CONFIG_PATH, 'utf-8'));

  const db = new DatabaseSync(dbPath);
  try {
    db.exec(`
      DELETE FROM orders;
      DELETE FROM sessions;
      DELETE FROM pizzas;
      DELETE FROM menus;
      DELETE FROM cpos;
      DELETE FROM admins;
    `);
    db.prepare(
      'INSERT INTO admins (id, username, password_hash, created_at, token_version) VALUES (1, ?, ?, ?, 0)'
    ).run(admin.username, admin.password_hash, admin.created_at);
  } finally {
    db.close();
  }
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
 * Creates a menu and adds pizzas to it via the API.
 *
 * @param {string} baseURL
 * @param {string} cpoToken - JWT returned after logging in as CPO
 * @param {Array<{ name: string, price: number }>} pizzas
 * @param {{ name?: string }} [opts] - menu name (default "Default"); the CPO's
 *   first menu automatically becomes the default menu.
 * @returns {Promise<{ menu: object, pizzas: object[] }>} MenuResponse + PizzaResponses
 */
export async function seedMenu(baseURL, cpoToken, pizzas, { name = 'Default' } = {}) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${cpoToken}`,
  };

  const menuRes = await fetch(`${baseURL}/api/cpo/menus`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ name }),
  });
  if (!menuRes.ok) {
    const text = await menuRes.text();
    throw new Error(`seedMenu failed creating menu "${name}" (${menuRes.status}): ${text}`);
  }
  const menu = await menuRes.json();

  const results = [];
  for (const pizza of pizzas) {
    const res = await fetch(`${baseURL}/api/cpo/menus/${menu.id}/pizzas`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name: pizza.name, price: pizza.price }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`seedMenu failed for "${pizza.name}" (${res.status}): ${text}`);
    }

    results.push(await res.json());
  }

  return { menu, pizzas: results };
}

// ---------------------------------------------------------------------------
// seedSession
// ---------------------------------------------------------------------------

/**
 * Creates a session via the CPO API.
 *
 * @param {string} baseURL
 * @param {string} cpoToken
 * @param {{ date: string, startTime: string, endTime: string, gracePeriodMinutes?: number, menuId?: string }} opts
 *   date format: "YYYY-MM-DD", time format: "HH:MM".
 *   menuId omitted → the server uses the CPO's default menu.
 * @returns {Promise<object>} SessionResponse JSON
 */
export async function seedSession(baseURL, cpoToken, { date, startTime, endTime, gracePeriodMinutes = 2, menuId = null }) {
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
      menu_id: menuId,
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
