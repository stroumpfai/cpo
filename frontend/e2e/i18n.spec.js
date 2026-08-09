/**
 * E2E tests for the multilingual UI.
 *
 * Two things are worth proving end-to-end that unit tests cannot:
 *
 *  1. Browser detection reaches a real browser. `test.use({ locale: 'de-CH' })`
 *     makes Chromium report `navigator.languages = ['de-CH']`, which is the
 *     only input `detectLanguage()` gets on a first visit — no localStorage,
 *     no account.
 *
 *  2. The account preference really lives in the database. The localStorage
 *     mirror (`cpo_lang`) would make a same-context re-login pass even if the
 *     column were never written, so the second login happens in a *fresh
 *     browser context* with no cookies and no localStorage.
 *
 * Isolation matches ordering.spec.js: the backend's SQLite rows are wiped and
 * re-seeded in beforeEach (see playwright.config.js for DATA_DIR/CONFIG_PATH).
 */

import { test, expect } from '@playwright/test';
import os from 'node:os';
import path from 'node:path';
import {
  resetDatabase,
  seedCpo,
  seedMenu,
  seedSession,
  setLanguage,
  loginAs,
  apiLogin,
  TEST_ADMIN,
} from './fixtures.js';

// Must match playwright.config.js (override both with E2E_PORT)
const BASE_URL = `http://localhost:${process.env.E2E_PORT ?? '8002'}`;

const E2E_TMP      = path.join(os.tmpdir(), 'cpo-e2e-test');
const E2E_DATA_DIR = path.join(E2E_TMP, 'data');

const TEST_CPO = {
  username: 'i18ncpo',
  // Must satisfy the password policy: no "cpo"/"pizza", no username
  password: 'TeamPass456!',
  email:    'i18ncpo@example.com',
  team_name: 'Test Team',
};

const PIZZAS = [
  { name: 'Margherita', price: 12.50 },
  { name: 'Pepperoni',  price: 14.00 },
];

function resetTestData() {
  resetDatabase(E2E_DATA_DIR);
}

// The API stores session date/times in UTC (the web form converts local → UTC
// before submitting), so fixtures must seed UTC values too.
function utcSessionWindow() {
  const now = new Date();
  const pad  = (n) => String(n).padStart(2, '0');
  const date = `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())}`;
  const startTime = `${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}`;
  const endTime   = `${pad((now.getUTCHours() + 2) % 24)}:${pad(now.getUTCMinutes())}`;
  return { date, startTime, endTime };
}

async function setupFullStack(adminToken) {
  const cpo = await seedCpo(BASE_URL, adminToken, TEST_CPO);
  const cpoToken = await apiLogin(BASE_URL, TEST_CPO.username, TEST_CPO.password);
  const { pizzas } = await seedMenu(BASE_URL, cpoToken, PIZZAS);
  const session = await seedSession(BASE_URL, cpoToken, {
    ...utcSessionWindow(),
    gracePeriodMinutes: 2,
  });
  return { cpo, cpoToken, session, pizzas };
}

// ---------------------------------------------------------------------------
// Scenario 15 — German team member on the public order page
// ---------------------------------------------------------------------------

test.describe('Scenario 15 — public order page in de-CH', () => {
  // A German-Swiss browser: no stored preference, no account — detection only.
  test.use({ locale: 'de-CH' });

  test.beforeEach(() => resetTestData());

  test('team member orders a plate with the page in German', async ({ page }) => {
    const adminToken = await apiLogin(BASE_URL, TEST_ADMIN.username, TEST_ADMIN.password);
    const { cpo } = await setupFullStack(adminToken);

    await page.goto(`${BASE_URL}/orders/${cpo.unique_link}`);

    // The detected language reaches <html lang>, not just the copy
    await expect(page.locator('html')).toHaveAttribute('lang', 'de-CH');

    // Header and the identity field the team asks for (name mode by default)
    await expect(page.locator('header')).toContainText('Bestelltag');
    await expect(page.locator('label[for="order-name"]')).toHaveText('Dein Name');
    await expect(page.locator('label[for="order-pizza"]')).toHaveText('Gericht auswählen');

    // Add a plate — the button, the cart heading and the remove title are German
    await page.fill('#order-name', 'Anna');
    await page.click('button:has-text("zur Bestellung hinzufügen")');
    await expect(page.locator('button[title="Entfernen"]')).toHaveCount(1);
    // Exact match: the plate <option> also reads "Margherita — CHF 12.50"
    await expect(page.getByText('CHF 12.50', { exact: true })).toBeVisible();

    // The per-IP rate limit is 1 submission per 5 s and is not reset with the
    // database, so leave the window from any preceding test behind.
    await page.waitForTimeout(5100);

    await page.click('button:has-text("Bestellung abschicken")');

    // Confirmation screen. The German copy deliberately drops the plate count
    // English carries, so this reads the same for one plate or five.
    await expect(page.locator('h1')).toContainText('Bestellung aufgegeben!');
    await expect(
      page.locator('text=Deine Bestellung wurde an den CPO übermittelt.')
    ).toBeVisible();
  });

  test('the closed-session state is German too', async ({ page }) => {
    const adminToken = await apiLogin(BASE_URL, TEST_ADMIN.username, TEST_ADMIN.password);
    const cpo = await seedCpo(BASE_URL, adminToken, TEST_CPO);
    const cpoToken = await apiLogin(BASE_URL, TEST_CPO.username, TEST_CPO.password);
    await seedMenu(BASE_URL, cpoToken, PIZZAS);

    // The API refuses to create sessions whose window already passed, so seed
    // an active session and force-close it.
    const session = await seedSession(BASE_URL, cpoToken, {
      ...utcSessionWindow(),
      gracePeriodMinutes: 0,
    });
    const closeRes = await fetch(`${BASE_URL}/api/cpo/sessions/${session.id}/close`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${cpoToken}` },
    });
    if (!closeRes.ok) throw new Error(`close session failed (${closeRes.status})`);

    await page.goto(`${BASE_URL}/orders/${cpo.unique_link}`);

    await expect(page.locator('text=Die Session ist geschlossen.')).toBeVisible();
    await expect(page.locator('text=Heute keine Bestellungen mehr.')).toBeVisible();
  });

  test('the switcher overrides detection and survives a reload', async ({ page }) => {
    const adminToken = await apiLogin(BASE_URL, TEST_ADMIN.username, TEST_ADMIN.password);
    const { cpo } = await setupFullStack(adminToken);

    await page.goto(`${BASE_URL}/orders/${cpo.unique_link}`);
    await expect(page.locator('label[for="order-name"]')).toHaveText('Dein Name');

    // Pick Italian in the header switcher
    await page.selectOption('header select', 'it-CH');
    await expect(page.locator('html')).toHaveAttribute('lang', 'it-CH');
    await expect(page.locator('label[for="order-name"]')).toHaveText('Il tuo nome');

    // The choice is mirrored to localStorage, so a reload keeps Italian even
    // though the browser still reports de-CH.
    await page.reload();
    await expect(page.locator('label[for="order-name"]')).toHaveText('Il tuo nome');
  });
});

// ---------------------------------------------------------------------------
// Scenario 16 — a CPO's language follows the account, not the browser
// ---------------------------------------------------------------------------

test.describe('Scenario 16 — account language persistence', () => {
  test.beforeEach(() => resetTestData());

  test('CPO picks French in Settings and finds it again in a clean browser', async ({ browser }) => {
    const adminToken = await apiLogin(BASE_URL, TEST_ADMIN.username, TEST_ADMIN.password);
    await setupFullStack(adminToken);

    // --- First browser: an English-speaking machine ---------------------
    const first = await browser.newContext({ locale: 'en-US' });
    const page = await first.newPage();

    await loginAs(page, BASE_URL, TEST_CPO.username, TEST_CPO.password);
    await expect(page.locator('.sidebar-nav')).toContainText('Dashboard');

    await page.goto(`${BASE_URL}/dashboard/settings`);
    // The form is hydrated from GET /cpo/me; picking a value before that
    // response lands would be overwritten by it.
    await expect(page.locator('#team-name-input')).toHaveValue(TEST_CPO.team_name);
    await page.selectOption('#language-input', 'fr-CH');
    await page.click('button:has-text("Save")');

    // Applies immediately, without a logout
    await expect(page.locator('.sidebar-nav')).toContainText('Tableau de bord');
    // The confirmation itself is rendered from a string captured while the
    // language switch was still in flight, so either language is correct here.
    await expect(page.getByText(/Enregistré\.|Saved\./)).toBeVisible();

    // Log out (the button is French by now)
    await page.click('button:has-text("se déconnecter")');
    await expect(page).toHaveURL(/\/login/);
    await first.close();

    // --- Second browser: no cookies, no localStorage, English locale ----
    // If the preference had only been mirrored into localStorage, this login
    // would come back English.
    const second = await browser.newContext({ locale: 'en-US' });
    const fresh = await second.newPage();

    await fresh.goto(`${BASE_URL}/login`);
    expect(await fresh.evaluate(() => localStorage.getItem('cpo_lang'))).toBeNull();

    await loginAs(fresh, BASE_URL, TEST_CPO.username, TEST_CPO.password);

    await expect(fresh.locator('.sidebar-nav')).toContainText('Tableau de bord');
    await expect(fresh.locator('.sidebar-nav')).toContainText('Statistiques');
    // …and the mirror is rebuilt from the account, not the other way round
    await expect(async () => {
      expect(await fresh.evaluate(() => localStorage.getItem('cpo_lang'))).toBe('fr-CH');
    }).toPass();

    await second.close();
  });

  test('a language set through the API greets the CPO at login', async ({ browser }) => {
    const adminToken = await apiLogin(BASE_URL, TEST_ADMIN.username, TEST_ADMIN.password);
    const { cpoToken } = await setupFullStack(adminToken);

    await setLanguage(BASE_URL, cpoToken, 'it-CH');

    const context = await browser.newContext({ locale: 'en-US' });
    const page = await context.newPage();
    await loginAs(page, BASE_URL, TEST_CPO.username, TEST_CPO.password);

    await expect(page.locator('.sidebar-nav')).toContainText('Statistiche');

    // Clearing it back to null returns the UI to the browser's language
    await setLanguage(BASE_URL, cpoToken, null);
    await page.evaluate(() => localStorage.removeItem('cpo_lang'));
    await page.reload();
    await expect(page.locator('.sidebar-nav')).toContainText('Statistics');

    await context.close();
  });
});
