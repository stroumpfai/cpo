import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

function RankedList({ title, rows, nameKey }) {
  const { t } = useTranslation();

  return (
    <div style={{ marginBottom: 12 }}>
      <div className="stat-label">{title}</div>
      {rows.length === 0 ? (
        <p className="text-soft text-sm">{t('stats.noOrders')}</p>
      ) : (
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          {rows.map(row => (
            <li key={row[nameKey]} className="text-sm">
              {row[nameKey]} <span className="text-soft mono">×{row.count}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

RankedList.propTypes = {
  title:   PropTypes.string.isRequired,
  rows:    PropTypes.array.isRequired,
  nameKey: PropTypes.string.isRequired,
};

export function MenuStatsCard({ menu }) {
  const { t } = useTranslation();

  return (
    <div className="card card-pad" style={{ minWidth: 260, flex: '1 1 320px' }}>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 600 }}>{menu.menu_name}</h3>
        <span className="text-soft text-xs">
          {t('stats.sessionCount', { count: menu.use_count })}
        </span>
      </div>

      <RankedList title={t('stats.topPlates')} rows={menu.top_plates} nameKey="pizza_name" />
      <RankedList title={t('stats.topPeople')} rows={menu.top_people} nameKey="member_name" />
    </div>
  );
}

MenuStatsCard.propTypes = {
  menu: PropTypes.shape({
    menu_id:   PropTypes.string.isRequired,
    menu_name: PropTypes.string.isRequired,
    use_count: PropTypes.number.isRequired,
    top_plates: PropTypes.arrayOf(PropTypes.shape({
      pizza_name: PropTypes.string.isRequired,
      count:      PropTypes.number.isRequired,
    })).isRequired,
    top_people: PropTypes.arrayOf(PropTypes.shape({
      member_name: PropTypes.string.isRequired,
      count:       PropTypes.number.isRequired,
    })).isRequired,
  }).isRequired,
};
