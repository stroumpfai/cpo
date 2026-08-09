import { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { utcHhmmToLocal } from '../utils/time.js';
import { formatDate } from '../utils/format.js';

const DATE_OPTS = { weekday: 'short', day: 'numeric', month: 'short' };

export function SessionHeader({ session, uniqueLink, onRefresh, onPrint }) {
  const [copied, setCopied] = useState(false);
  const { t, i18n } = useTranslation();

  function copyLink() {
    const url = `${globalThis.location.origin}/orders/${uniqueLink}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  // Times are stored in UTC — convert to local for display
  const date  = session.session_date;
  const graceM = session.grace_period_minutes ?? 2;

  const localStart = utcHhmmToLocal(date, session.start_time);

  // Compute UTC close time (end + grace), then convert to local
  const [endH, endM] = session.end_time.split(':').map(Number);
  const closeMin = endM + graceM;
  const closeUtcH = endH + Math.floor(closeMin / 60);
  const closeUtcHhmm = `${String(closeUtcH % 24).padStart(2, '0')}:${String(closeMin % 60).padStart(2, '0')}`;
  const localClose = utcHhmmToLocal(date, closeUtcHhmm);

  return (
    <div className="page-header" style={{ alignItems: 'flex-start', marginBottom: 20 }}>
      <div>
        <h1 className="page-title">{t('dashboard.title')}</h1>
        <p className="page-subtitle">
          {t('dashboard.sessionOn', { date: formatDate(date, i18n.language, DATE_OPTS) })}
          &nbsp;·&nbsp;
          {localStart} — {localClose}
          &nbsp;
          <span className="text-faint">{t('dashboard.graceNote', { minutes: graceM })}</span>
        </p>
      </div>
      <div className="row" style={{ gap: 8, flexShrink: 0 }}>
        <button className="btn" onClick={onRefresh} title={t('dashboard.refreshTitle')}>{t('dashboard.refresh')}</button>
        <button className="btn btn-ghost" onClick={onPrint} title={t('dashboard.printTitle')}>{t('dashboard.print')}</button>
        <button
          className="btn btn-primary"
          onClick={copyLink}
          title={t('dashboard.copyLinkTitle')}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}
        >
          {copied ? t('dashboard.copied') : `🔗 /orders/${uniqueLink}`}
        </button>
      </div>
    </div>
  );
}

SessionHeader.propTypes = {
  session: PropTypes.shape({
    session_date:         PropTypes.string.isRequired,
    start_time:           PropTypes.string.isRequired,
    end_time:             PropTypes.string.isRequired,
    grace_period_minutes: PropTypes.number,
  }).isRequired,
  uniqueLink: PropTypes.string.isRequired,
  onRefresh:  PropTypes.func.isRequired,
  onPrint:    PropTypes.func.isRequired,
};
