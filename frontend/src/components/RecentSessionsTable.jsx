import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { formatDate } from '../utils/format.js';

const DATE_OPTS = { weekday: 'short', day: 'numeric', month: 'short' };

// 'upcoming' | 'active' | 'closed' → the same wording the new-session banner uses
const STATUS_KEY = {
  upcoming: 'session.statusUpcoming',
  active:   'session.statusActive',
  closed:   'session.statusClosed',
};

export function RecentSessionsTable({ rows }) {
  const { t, i18n } = useTranslation();

  if (rows.length === 0) {
    return (
      <div className="card card-pad text-soft text-sm">
        {t('stats.noSessions')}
      </div>
    );
  }

  return (
    <div className="card table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>{t('stats.colDate')}</th>
            <th>{t('stats.colTime')}</th>
            <th>{t('stats.colStatus')}</th>
            <th style={{ textAlign: 'right' }}>{t('stats.colItems')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.session_id}>
              <td>{formatDate(row.session_date, i18n.language, DATE_OPTS)}</td>
              <td className="td-mono">{row.start_time}–{row.end_time}</td>
              <td className={row.status === 'active' ? 'text-accent' : 'text-soft'}>
                {t(STATUS_KEY[row.status])}
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
