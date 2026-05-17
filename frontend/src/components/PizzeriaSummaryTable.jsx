import PropTypes from 'prop-types';

export function PizzeriaSummaryTable({ rows, totalOrders, totalPrice }) {
  if (rows.length === 0) {
    return (
      <div className="card card-pad text-soft text-sm">
        No orders yet.
      </div>
    );
  }

  const maxCount = Math.max(...rows.map(r => r.count), 1);

  return (
    <div className="card table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>pizza</th>
            <th>count</th>
            <th style={{ textAlign: 'right' }}>total (CHF)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.pizza_name}>
              <td>{row.pizza_name}</td>
              <td>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  <span className="mono" style={{ width: 24, textAlign: 'right' }}>{row.count}</span>
                  <div className="pizzeria-bar" style={{
                    flex: 1, maxWidth: 160, height: 10,
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 999, overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%',
                      width: `${(row.count / maxCount) * 100}%`,
                      background: 'var(--color-accent)',
                      borderRadius: 999,
                    }} />
                  </div>
                </div>
              </td>
              <td className="mono" style={{ textAlign: 'right' }}>{row.total_price.toFixed(2)}</td>
            </tr>
          ))}
          <tr style={{ fontWeight: 700, background: 'var(--color-surface)' }}>
            <td>total</td>
            <td className="mono">{totalOrders}</td>
            <td className="mono" style={{ textAlign: 'right' }}>{totalPrice.toFixed(2)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

const rowShape = PropTypes.shape({
  pizza_name:  PropTypes.string.isRequired,
  count:       PropTypes.number.isRequired,
  total_price: PropTypes.number.isRequired,
});

PizzeriaSummaryTable.propTypes = {
  rows:        PropTypes.arrayOf(rowShape).isRequired,
  totalOrders: PropTypes.number.isRequired,
  totalPrice:  PropTypes.number.isRequired,
};
