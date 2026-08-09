import { DEFAULT_LOCALE, SUPPORTED_TAGS } from './locales.js';

/** The browser's preferred languages, most-preferred first. */
export function browserLanguages() {
  const nav = globalThis.navigator;
  if (!nav) return [];
  if (Array.isArray(nav.languages) && nav.languages.length) return nav.languages;
  return nav.language ? [nav.language] : [];
}

function primary(tag) {
  return tag.split('-')[0].toLowerCase();
}

/**
 * Pick a shipped locale for a browser's language list.
 *
 * Exact tag wins ("fr-CH" → fr-CH); otherwise the primary subtag decides, so
 * every German browser lands on Swiss German ("de", "de-DE", "de-AT" → de-CH).
 * Anything we don't ship falls back to English.
 */
export function detectLanguage(languages = browserLanguages()) {
  const list = Array.isArray(languages) ? languages : [];

  for (const raw of list) {
    if (typeof raw !== 'string') continue;
    const tag = raw.trim();
    if (!tag) continue;

    const exact = SUPPORTED_TAGS.find(t => t.toLowerCase() === tag.toLowerCase());
    if (exact) return exact;

    const byPrimary = SUPPORTED_TAGS.find(t => primary(t) === primary(tag));
    if (byPrimary) return byPrimary;
  }

  return DEFAULT_LOCALE;
}
