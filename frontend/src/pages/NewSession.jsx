import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Trans, useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { translateApiError } from '../i18n/apiError.js';
import { localHhmmToUtc, utcHhmmToLocal } from '../utils/time.js';

function today() {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0'),
  ].join('-');
}

function hhmm(d) {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function defaultStartTime() {
  return hhmm(new Date());
}

// Clamped to 23:59 rather than wrapping into tomorrow: sessions are a single
// calendar day (see spansMidnight), so an unclamped "an hour from now" would
// pre-fill an end time the form itself rejects whenever the page is opened
// after 23:00.
function defaultEndTime() {
  const d = new Date();
  const mins = Math.min(d.getHours() * 60 + d.getMinutes() + 60, 23 * 60 + 59);
  return `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
}

// Sessions are combined with their date as a single calendar day (see the
// backend's utils.session_datetime) — end <= start would place the close
// instant before the session opens, so it would never go "active".
function spansMidnight(startTimeStr, endTimeStr) {
  return endTimeStr <= startTimeStr;
}

// Returns true if the session close time (end + grace) has already passed.
function isAlreadyClosed(dateStr, endTimeStr, graceMins) {
  const [y, m, day] = dateStr.split('-').map(Number);
  const [h, min]    = endTimeStr.split(':').map(Number);
  const closeMs = new Date(y, m - 1, day, h, min).getTime() + graceMins * 60_000;
  return closeMs < Date.now();
}

function computeCutoff(endTime, graceMins) {
  if (!endTime) return '';
  const [h, m] = endTime.split(':').map(Number);
  const total  = h * 60 + m + graceMins;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

export function NewSession() {
  const [date, setDate]           = useState(today());
  const [startTime, setStartTime] = useState(defaultStartTime);
  const [endTime, setEndTime]     = useState(defaultEndTime);
  const [grace, setGrace]         = useState(2);
  const [cpo, setCpo]             = useState(null);
  const [error, setError]         = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied]       = useState(false);

  // Menus: the session serves exactly one; the default menu is preselected
  const [menus, setMenus]         = useState(null);   // null = still loading
  const [menuId, setMenuId]       = useState('');

  // Running session (active or upcoming) detected on mount
  const [runningSession, setRunningSession] = useState(null);
  const [closing, setClosing]              = useState(false);
  const [closeError, setCloseError]        = useState('');

  const navigate = useNavigate();
  const { t } = useTranslation();

  async function loadSessions() {
    try {
      const sessions = await api.get('/cpo/sessions');
      const running = sessions.find(s => s.status === 'active' || s.status === 'upcoming') ?? null;
      setRunningSession(running);
    } catch { /* ignore — form still usable */ }
  }

  useEffect(() => {
    api.get('/cpo/me').then(setCpo).catch(() => {});
    api.get('/cpo/menus').then(list => {
      setMenus(list);
      setMenuId((list.find(m => m.is_default) ?? list[0])?.id ?? '');
    }).catch(() => setMenus([]));
    loadSessions();
  }, []);

  const cutoff = useMemo(() => computeCutoff(endTime, grace), [endTime, grace]);

  const teamLink = cpo
    ? `${globalThis.location.origin}/orders/${cpo.unique_link}`
    : '…';

  function copyLink() {
    navigator.clipboard.writeText(teamLink).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  async function closeRunningSession() {
    if (!runningSession) return;
    setCloseError('');
    setClosing(true);
    try {
      await api.post(`/cpo/sessions/${runningSession.id}/close`);
      setRunningSession(null);
    } catch (err) {
      setCloseError(translateApiError(err, t));
    } finally {
      setClosing(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    if (spansMidnight(startTime, endTime)) {
      // Same wording (and key) the backend uses when it rejects the window
      setError(t('errors.end_before_start'));
      return;
    }

    if (isAlreadyClosed(date, endTime, grace)) {
      setError(t('errors.sessionAlreadyPassed'));
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/cpo/sessions', {
        session_date: date,
        start_time: localHhmmToUtc(date, startTime),
        end_time:   localHhmmToUtc(date, endTime),
        grace_period_minutes: grace,
        menu_id: menuId || null,
      });
      navigate('/dashboard');
    } catch (err) {
      setError(translateApiError(err, t));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('session.title')}</h1>
          <p className="page-subtitle">
            {t('session.subtitle')}
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* No menus yet — a session needs one */}
      {menus !== null && menus.length === 0 && (
        <div className="alert alert-error" style={{ marginBottom: 16, maxWidth: 560 }}>
          {t('session.needMenu')}{' '}
          <Link to="/dashboard/menus">{t('menus.title')}</Link>.
        </div>
      )}

      {/* Running session banner — only shown when a session is active or upcoming */}
      {runningSession && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 16, padding: '12px 16px', marginBottom: 20, maxWidth: 560,
          background: 'var(--color-accent-soft)',
          border: '1px solid var(--color-accent)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div>
            <span style={{ fontWeight: 600, color: 'var(--color-accent)' }}>
              {t('session.alreadyRunning', {
                status: t(runningSession.status === 'active'
                  ? 'session.statusActive'
                  : 'session.statusUpcoming'),
              })}
            </span>
            <div className="text-soft text-sm" style={{ marginTop: 2 }}>
              {runningSession.session_date} · {utcHhmmToLocal(runningSession.session_date, runningSession.start_time)} — {utcHhmmToLocal(runningSession.session_date, runningSession.end_time)}
            </div>
            {closeError && (
              <div className="text-sm" style={{ color: 'var(--color-accent-dark)', marginTop: 4 }}>
                {closeError}
              </div>
            )}
          </div>
          <button
            type="button"
            className="btn btn-primary"
            style={{ flexShrink: 0 }}
            onClick={closeRunningSession}
            disabled={closing}
          >
            {closing ? t('session.closing') : t('session.closeRunning')}
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ maxWidth: 560 }}>
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          {/* Date + times */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div className="form-group">
              <label className="form-label" htmlFor="sess-date">{t('session.date')}</label>
              <input
                id="sess-date" className="form-input" type="date" required
                value={date} onChange={e => setDate(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="sess-start">{t('session.startTime')}</label>
              <input
                id="sess-start" className="form-input" type="time" required
                value={startTime} onChange={e => setStartTime(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="sess-end">{t('session.endTime')}</label>
              <input
                id="sess-end" className="form-input" type="time" required
                value={endTime} onChange={e => setEndTime(e.target.value)}
              />
            </div>
          </div>

          {/* Menu served during the session */}
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label" htmlFor="sess-menu">{t('session.menu')}</label>
            <select
              id="sess-menu"
              className="form-input"
              value={menuId}
              onChange={e => setMenuId(e.target.value)}
              disabled={!menus || menus.length === 0}
            >
              {(menus ?? []).map(m => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {/* Grace period stepper */}
          <div className="row" style={{ gap: 16, marginBottom: 16, alignItems: 'center' }}>
            <div className="form-group" style={{ flexShrink: 0 }}>
              <span className="form-label" style={{ display: 'block', marginBottom: 5 }}>{t('session.gracePeriod')}</span>
              <div className="row" style={{ gap: 6 }}>
                <button
                  type="button" className="btn"
                  style={{ padding: '6px 12px' }}
                  onClick={() => setGrace(g => Math.max(0, g - 1))}
                >−</button>
                <span className="mono" style={{ minWidth: 28, textAlign: 'center', fontWeight: 600, fontSize: 16 }}>
                  {grace}
                </span>
                <button
                  type="button" className="btn"
                  style={{ padding: '6px 12px' }}
                  onClick={() => setGrace(g => g + 1)}
                >+</button>
                <span className="text-soft text-sm">{t('session.minutesShort')}</span>
              </div>
            </div>
            {cutoff && (
              <p className="text-faint text-sm" style={{ marginTop: 18 }}>
                {/* Trans keeps the mono-styled time inline while letting each
                    language put it wherever the sentence needs it. */}
                <Trans
                  i18nKey="session.cutoffNote"
                  values={{ time: cutoff }}
                  components={{ mono: <span className="mono" /> }}
                />
              </p>
            )}
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '4px 0 16px' }} />

          {/* Team link */}
          <div className="form-group">
            <label className="form-label" htmlFor="team-link">
              {t('session.teamLinkLabel')}
            </label>
            <div className="row" style={{ gap: 8 }}>
              <input
                id="team-link"
                className="form-input form-input-mono"
                readOnly
                value={teamLink}
                style={{ flex: 1, fontSize: 'var(--font-size-sm)' }}
              />
              <button type="button" className="btn" onClick={copyLink}>
                {copied ? t('session.copied') : t('session.copy')}
              </button>
            </div>
          </div>
        </div>

        <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" className="btn" onClick={() => navigate('/dashboard')}>{t('common.cancel')}</button>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || !menus || menus.length === 0}
          >
            {submitting ? t('session.submitting') : t('session.submit')}
          </button>
        </div>
      </form>
    </div>
  );
}
