import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { DEFAULT_LOCALE, LOCALES, SUPPORTED_TAGS } from './locales.js';
import { detectLanguage } from './detect.js';
import { getStoredLanguage, setStoredLanguage } from './storage.js';

// Every language is bundled, not lazy-loaded: the payload is a few tens of KB in
// a single-container app, and synchronous init keeps components (and tests) free
// of Suspense boilerplate.
const resources = Object.fromEntries(
  LOCALES.map(({ tag, resource }) => [tag, { translation: resource }])
);

/** Stored choice (member pick or cached account preference) → browser → English. */
export function resolveInitialLanguage() {
  return getStoredLanguage() ?? detectLanguage();
}

i18n.use(initReactI18next).init({
  resources,
  lng: resolveInitialLanguage(),
  fallbackLng: DEFAULT_LOCALE,
  supportedLngs: SUPPORTED_TAGS,
  interpolation: { escapeValue: false },   // React already escapes
});

/**
 * Switch language and remember the choice.
 *
 * `null` means "follow my browser": the mirror is cleared and detection decides.
 * Returns the tag that ended up active.
 */
export function applyLanguage(tag) {
  setStoredLanguage(tag ?? null);
  const next = tag ?? detectLanguage();
  if (i18n.language !== next) i18n.changeLanguage(next);
  return next;
}

// Same behaviour, named for the call sites that feed it an account preference
// (GET /cpo/me, GET /admin/me), where `null` = the account follows the browser.
export const applyAccountLanguage = applyLanguage;

export default i18n;
