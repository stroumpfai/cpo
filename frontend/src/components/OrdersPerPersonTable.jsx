import PropTypes from 'prop-types';

function fmtTime(isoStr) {
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '—';
  }
}

export function OrdersPerPersonTable({ rows, paidSet, onTogglePaid, onDelete, isClosed, printMode }) {
  const sorted = [...rows].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  if (sorted.length === 0) {
    return (
      <div className="card card-pad text-soft text-sm">
        No orders yet — waiting for team members to submit.
      </div>
    );
  }

  if (printMode) {
    return (
      <div className="card table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>time ↓</th>
              <th>member</th>
              <th>pizza</th>
              <th style={{ textAlign: 'right' }}>price (CHF)</th>
              <th>received</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => (
              <tr key={row.order_id}>
                <td className="td-mono">{fmtTime(row.created_at)}</td>
                <td style={{ fontWeight: 500 }}>{row.member_name}</td>
                <td>
                  {row.pizza_name}
                  {row.comment && (
                    <span className="order-comment">{row.comment}</span>
                  )}
                </td>
                <td className="td-mono" style={{ textAlign: 'right' }}>{row.price.toFixed(2)}</td>
                <td style={{ textAlign: 'center' }}>{paidSet.has(row.order_id) ? '✓' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="card table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>time ↓</th>
            <th>member</th>
            <th>client ip</th>
            <th>pizza</th>
            <th style={{ textAlign: 'right' }}>price (CHF)</th>
            <th>{isClosed ? 'received' : 'action'}</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => {
            const paid = paidSet.has(row.order_id);
            return (
              <tr key={row.order_id}>
                <td className="td-mono">{fmtTime(row.created_at)}</td>
                <td style={{ fontWeight: 500 }}>{row.member_name}</td>
                <td className="td-mono">{row.client_ip}</td>
                <td>
                  {row.pizza_name}
                  {row.comment && (
                    <span className="order-comment">{row.comment}</span>
                  )}
                </td>
                <td className="td-mono" style={{ textAlign: 'right' }}>{row.price.toFixed(2)}</td>
                <td>
                  <div className="row" style={{ gap: 10 }}>
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: 'var(--font-size-xs)', padding: '3px 8px', color: paid ? 'var(--color-accent)' : 'var(--color-text-soft)' }}
                      onClick={() => onTogglePaid(row.order_id)}
                      title={paid ? 'Mark unpaid' : 'Mark paid'}
                    >
                      {paid ? '✓ received' : '💰 received'}
                    </button>
                    {!isClosed && (
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 'var(--font-size-xs)', padding: '3px 8px', color: 'var(--color-accent)' }}
                        onClick={() => onDelete(row.order_id)}
                        title="Delete order"
                      >
                        ✕ delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const rowShape = PropTypes.shape({
  order_id:    PropTypes.string.isRequired,
  member_name: PropTypes.string.isRequired,
  client_ip:   PropTypes.string.isRequired,
  pizza_name:  PropTypes.string.isRequired,
  price:       PropTypes.number.isRequired,
  created_at:  PropTypes.string.isRequired,
  comment:     PropTypes.string,
});

OrdersPerPersonTable.propTypes = {
  rows:         PropTypes.arrayOf(rowShape).isRequired,
  paidSet:      PropTypes.instanceOf(Set).isRequired,
  onTogglePaid: PropTypes.func.isRequired,
  onDelete:     PropTypes.func.isRequired,
  isClosed:     PropTypes.bool.isRequired,
  printMode:    PropTypes.bool,
};
