import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

export function StatCards({ memberCount, pizzaCount, totalPrice, countdown, countdownPct, isClosed, currency }) {
  const { t } = useTranslation();

  return (
    <div className="stat-cards" style={{ marginBottom: 20 }}>
      <StatCard label={t('dashboard.members')} value={memberCount} />
      <StatCard label={t('dashboard.plates')}  value={pizzaCount} />
      <StatCard label={t('dashboard.currencyTotal', { currency })} value={totalPrice.toFixed(2)} mono />
      <CountdownCard countdown={countdown} pct={countdownPct} isClosed={isClosed} />
    </div>
  );
}

StatCards.propTypes = {
  memberCount:   PropTypes.number.isRequired,
  pizzaCount:    PropTypes.number.isRequired,
  totalPrice:    PropTypes.number.isRequired,
  countdown:     PropTypes.string.isRequired,
  countdownPct:  PropTypes.number.isRequired,
  isClosed:      PropTypes.bool.isRequired,
  currency:      PropTypes.string.isRequired,
};

function StatCard({ label, value, mono = false }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${mono ? ' mono' : ''}`}>{value}</div>
    </div>
  );
}

StatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  mono:  PropTypes.bool,
};

function CountdownCard({ countdown, pct, isClosed }) {
  const { t } = useTranslation();

  return (
    <div className="stat-card stat-card-accent">
      <div className="row" style={{ marginBottom: 4 }}>
        <span style={{ fontSize: 13 }}>⏱</span>
        <span className="stat-label" style={{ color: 'var(--color-accent)', margin: 0 }}>
          {isClosed ? t('dashboard.sessionClosed') : t('dashboard.endsIn')}
        </span>
        {!isClosed && (
          <span className="chip chip-live" style={{ marginLeft: 'auto', gap: 4, fontSize: 9 }}>
            <span className="pulse-dot" />{t('dashboard.live')}
          </span>
        )}
      </div>
      <div className="stat-value mono stat-value-accent" style={{ fontSize: 32 }}>
        {isClosed ? '—' : countdown}
      </div>
      {!isClosed && (
        <div style={{
          height: 4, background: 'rgba(255,255,255,.5)',
          borderRadius: 2, marginTop: 8, overflow: 'hidden',
        }}>
          <div style={{
            height: '100%', width: `${pct}%`,
            background: 'var(--color-accent)', transition: 'width 1s linear',
          }} />
        </div>
      )}
    </div>
  );
}

CountdownCard.propTypes = {
  countdown: PropTypes.string.isRequired,
  pct:       PropTypes.number.isRequired,
  isClosed:  PropTypes.bool.isRequired,
};
