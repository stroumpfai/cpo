import PropTypes from 'prop-types';

function fmtDate(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: 'short', day: 'numeric', month: 'short',
  });
}

export function RecentSessionsTable({ rows }) {
  if (rows.length === 0) {
    return (
      <div className="card card-pad text-soft text-sm">
        No sessions yet.
      </div>
    );
  }

  return (
    <div className="card table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>date</th>
            <th>time</th>
            <th>status</th>
            <th style={{ textAlign: 'right' }}>items</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.session_id}>
              <td>{fmtDate(row.session_date)}</td>
              <td className="td-mono">{row.start_time}–{row.end_time}</td>
              <td className={row.status === 'active' ? 'text-accent' : 'text-soft'}>
                {row.status}
              </td>
              <td className="mono" style={{ textAlign: 'right' }}>{row.item_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const rowShape = PropTypes.shape({
  session_id:  PropTypes.string.isRequired,
  session_date: PropTypes.string.isRequired,
  start_time:  PropTypes.string.isRequired,
  end_time:    PropTypes.string.isRequired,
  status:      PropTypes.oneOf(['upcoming', 'active', 'closed']).isRequired,
  item_count:  PropTypes.number.isRequired,
});

RecentSessionsTable.propTypes = {
  rows: PropTypes.arrayOf(rowShape).isRequired,
};
