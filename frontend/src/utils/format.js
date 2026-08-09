/**
 * Locale-aware date/time formatting.
 *
 * These wrap Intl with the *chosen* language rather than the browser's: a CPO
 * who picked Deutsch on an English laptop should read 01.08.2026, not 8/1/2026.
 * Pass i18n.language from the calling component.
 *
 * Prices are deliberately not routed through Intl — CHF is written 12.50 in all
 * four locales, and the summary tables align on a fixed two-decimal string.
 */

/** "YYYY-MM-DD" → a locale-formatted date (weekday + day + month by default). */
export function formatDate(dateStr, locale, options = { weekday: 'short', day: '2-digit', month: 'short' }) {
  if (!dateStr) return '';
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(locale, options);
}

/** An ISO timestamp → a locale-formatted calendar date. */
export function formatIsoDate(iso, locale, options = undefined) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString(locale, options);
}

/** An ISO timestamp → a locale-formatted wall-clock time. */
export function formatTime(iso, locale, options = { hour: '2-digit', minute: '2-digit', second: '2-digit' }) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString(locale, options);
}

/** An ISO timestamp → a locale-formatted date and time. */
export function formatDateTime(iso, locale, options = undefined) {
  if (!iso) return '';
  return new Date(iso).toLocaleString(locale, options);
}
