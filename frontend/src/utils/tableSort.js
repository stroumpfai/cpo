import { useCallback, useState } from 'react';

// Column sorting for the dashboard summary tables. The state lives in the page
// (not in the table) because the print-only block renders a *second* instance of
// each table — both must be handed the same sort so the print-out matches the
// screen.

// Columns that are most useful "biggest / newest first" on the initial click.
const DESC_FIRST = new Set(['created_at', 'price', 'count', 'total_price', 'received']);

export function useTableSort(defaultKey, defaultDir = 'asc') {
  const [sort, setSort] = useState({ key: defaultKey, dir: defaultDir });

  const toggleSort = useCallback(key => {
    setSort(prev => prev.key === key
      ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: DESC_FIRST.has(key) ? 'desc' : 'asc' });
  }, []);

  return { sortKey: sort.key, sortDir: sort.dir, toggleSort };
}

// Zero-pads the numeric groups of an IPv4 address so plain string comparison
// orders it numerically (10.0.0.9 before 10.0.0.10). Anything else — IPv6, a
// proxy chain — falls through and is compared as text.
export function ipSortKey(ip) {
  const str = String(ip ?? '');
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(str)
    ? str.split('.').map(part => part.padStart(3, '0')).join('.')
    : str;
}

function isBlank(value) {
  return value === null || value === undefined || value === '';
}

// Ascending comparison: false before true, smaller before larger, A before Z.
function compare(a, b) {
  if (typeof a === 'boolean' || typeof b === 'boolean') {
    return Number(a) - Number(b);
  }
  if (typeof a === 'number' && typeof b === 'number') {
    return a - b;
  }
  return String(a).localeCompare(String(b), undefined, { sensitivity: 'base', numeric: true });
}

/**
 * Sorts a copy of `rows` by `sortKey` using `accessors[sortKey]` to read the
 * comparable value. Ties fall back to newest-first, then id, so the order stays
 * stable while SSE keeps replacing the row array.
 */
export function sortRows(rows, sortKey, sortDir, accessors) {
  const read = Object.hasOwn(accessors, sortKey) ? accessors[sortKey] : null;
  const flip = sortDir === 'desc' ? -1 : 1;

  return [...rows].sort((rowA, rowB) => {
    if (read) {
      const a = read(rowA);
      const b = read(rowB);
      // Blanks sink to the bottom whichever direction is active, so their verdict
      // is returned unflipped.
      if (isBlank(a) || isBlank(b)) {
        if (!isBlank(a)) return -1;
        if (!isBlank(b)) return 1;
      } else {
        const primary = compare(a, b);
        if (primary !== 0) return primary * flip;
      }
    }
    const timeDiff = new Date(rowB.created_at ?? 0) - new Date(rowA.created_at ?? 0);
    if (timeDiff) return timeDiff;
    return String(rowA.order_id ?? '').localeCompare(String(rowB.order_id ?? ''));
  });
}
