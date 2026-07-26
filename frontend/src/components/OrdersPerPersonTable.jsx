import PropTypes from 'prop-types';
import { SortableTh } from './SortableTh.jsx';
import { ipSortKey, sortRows } from '../utils/tableSort.js';

function fmtTime(isoStr) {
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '—';
  }
}

export function OrdersPerPersonTable({
  rows, paidSet, onTogglePaid, onDelete, isClosed, printMode, currency,
  sortKey = 'created_at', sortDir = 'desc', onSort,
}) {
  const sorted = sortRows(rows, sortKey, sortDir, {
    created_at:  row => new Date(row.created_at).getTime(),
    member_name: row => row.member_name,
    client_ip:   row => ipSortKey(row.client_ip),
    pizza_name:  row => row.pizza_name,
    price:       row => row.price,
    received:    row => paidSet.has(row.order_id),
  });

  // Shared by both render branches below — print drops `client ip` but keeps the
  // same sort keys, so the order the CPO picked on screen carries into the sheet.
  const th = (label, key, align) => (
    <SortableTh label={label} sortKey={key} activeKey={sortKey} dir={sortDir} onSort={onSort} align={align} />
  );

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
              {th('time', 'created_at')}
              {th('member', 'member_name')}
              {th('plate', 'pizza_name')}
              {th(`price (${currency})`, 'price', 'right')}
              {th('received', 'received')}
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => (
              <tr key={row.order_id}>
                <td className="td-mono">{fmtTime(row.created_at)}</td>
                {/* overflowWrap: emails run ~3x longer than first names */}
                <td style={{ fontWeight: 500, overflowWrap: 'anywhere' }}>{row.member_name}</td>
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
            {th('time', 'created_at')}
            {th('member', 'member_name')}
            {th('client ip', 'client_ip')}
            {th('plate', 'pizza_name')}
            {th(`price (${currency})`, 'price', 'right')}
            {th(isClosed ? 'received' : 'action', 'received')}
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => {
            const paid = paidSet.has(row.order_id);
            return (
              <tr key={row.order_id}>
                <td className="td-mono">{fmtTime(row.created_at)}</td>
                {/* overflowWrap: emails run ~3x longer than first names */}
                <td style={{ fontWeight: 500, overflowWrap: 'anywhere' }}>{row.member_name}</td>
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
  currency:     PropTypes.string.isRequired,
  sortKey:      PropTypes.string,
  sortDir:      PropTypes.oneOf(['asc', 'desc']),
  onSort:       PropTypes.func,
};
