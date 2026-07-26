import PropTypes from 'prop-types';

// Clickable column header for `.data-table`. Without `onSort` it degrades to a
// plain header cell, so the tables stay usable outside the dashboard page.
export function SortableTh({ label, sortKey, activeKey, dir, onSort, align = 'left' }) {
  const style  = align === 'left' ? undefined : { textAlign: align };
  const active = sortKey === activeKey;

  if (!onSort) {
    return <th style={style}>{label}</th>;
  }

  return (
    <th style={style} aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}>
      <button
        type="button"
        className="th-sort"
        onClick={() => onSort(sortKey)}
        title={`Sort by ${label}`}
      >
        {label}
        <span className={`sort-arrow${active ? '' : ' sort-arrow-idle'}`} aria-hidden="true">
          {active && dir === 'asc' ? '↑' : '↓'}
        </span>
      </button>
    </th>
  );
}

SortableTh.propTypes = {
  label:     PropTypes.string.isRequired,
  sortKey:   PropTypes.string.isRequired,
  activeKey: PropTypes.string,
  dir:       PropTypes.oneOf(['asc', 'desc']),
  onSort:    PropTypes.func,
  align:     PropTypes.oneOf(['left', 'right', 'center']),
};
