/**
 * Time-zone conversion helpers.
 *
 * Session times are stored on the server in UTC (HH:MM strings).
 * The browser knows the user's local offset and converts:
 *   - local → UTC before submitting
 *   - UTC  → local before displaying
 */

/** Convert a local HH:MM on dateStr to UTC HH:MM. */
export function localHhmmToUtc(dateStr, localHhmm) {
  const [y, mo, d] = dateStr.split('-').map(Number);
  const [h, m]     = localHhmm.split(':').map(Number);
  const dt = new Date(y, mo - 1, d, h, m);   // local instant
  return `${String(dt.getUTCHours()).padStart(2, '0')}:${String(dt.getUTCMinutes()).padStart(2, '0')}`;
}

/** Convert a UTC HH:MM on dateStr to local HH:MM for display. */
export function utcHhmmToLocal(dateStr, utcHhmm) {
  const [y, mo, d] = dateStr.split('-').map(Number);
  const [h, m]     = utcHhmm.split(':').map(Number);
  const dt = new Date(Date.UTC(y, mo - 1, d, h, m));
  return `${String(dt.getHours()).padStart(2, '0')}:${String(dt.getMinutes()).padStart(2, '0')}`;
}

/** Return UTC epoch-ms for a UTC HH:MM on dateStr (for countdown arithmetic). */
export function parseUtcDt(dateStr, utcHhmm) {
  const [y, mo, d] = dateStr.split('-').map(Number);
  const [h, m]     = utcHhmm.split(':').map(Number);
  return Date.UTC(y, mo - 1, d, h, m);
}
