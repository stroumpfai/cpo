import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { SortableTh } from './SortableTh.jsx';
import { ipSortKey, sortRows } from '../utils/tableSort.js';
import { formatTime } from '../utils/format.js';

function fmtTime(isoStr, locale) {
  try {
    return formatTime(isoStr, locale);
  } catch {
    return '—';
  }
}

export function OrdersPerPersonTable({
  rows, paidSet, onTogglePaid, onDelete, isClosed, printMode, currency,
  sortKey = 'created_at', sortDir = 'desc', onSort,
}) {
  const { t, i18n } = useTranslation();

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
        {t('dashboard.noOrders')}
      </div>
    );
  }

  if (printMode) {
    return (
      <div className="card table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              {th(t('dashboard.colTime'), 'created_at')}
              {th(t('dashboard.colMember'), 'member_name')}
              {th(t('dashboard.colPlate'), 'pizza_name')}
              {th(t('dashboard.colPrice', { currency: currency ?? '' }), 'price', 'right')}
              {th(t('dashboard.colReceived'), 'received')}
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => (
              <tr key={row.order_id}>
                <td className="td-mono">{fmtTime(row.created_at, i18n.language)}</td>
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
            {th(t('dashboard.colTime'), 'created_at')}
            {th(t('dashboard.colMember'), 'member_name')}
            {th(t('dashboard.colClientIp'), 'client_ip')}
            {th(t('dashboard.colPlate'), 'pizza_name')}
            {th(t('dashboard.colPrice', { currency: currency ?? '' }), 'price', 'right')}
            {th(isClosed ? t('dashboard.colReceived') : t('dashboard.colAction'), 'received')}
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => {
            const paid = paidSet.has(row.order_id);
            return (
              <tr key={row.order_id}>
                <td className="td-mono">{fmtTime(row.created_at, i18n.language)}</td>
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
                      title={paid ? t('dashboard.markUnpaid') : t('dashboard.markPaid')}
                    >
                      {paid ? t('dashboard.receivedYes') : t('dashboard.receivedNo')}
                    </button>
                    {!isClosed && (
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: 'var(--font-size-xs)', padding: '3px 8px', color: 'var(--color-accent)' }}
                        onClick={() => onDelete(row.order_id)}
                        title={t('dashboard.deleteOrderTitle')}
                      >
                        {t('dashboard.deleteOrder')}
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
