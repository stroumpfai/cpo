import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';

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

function defaultEndTime() {
  const d = new Date();
  d.setHours(d.getHours() + 1);
  return hhmm(d);
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

  // Running session (active or upcoming) detected on mount
  const [runningSession, setRunningSession] = useState(null);
  const [closing, setClosing]              = useState(false);
  const [closeError, setCloseError]        = useState('');

  const navigate = useNavigate();

  async function loadSessions() {
    try {
      const sessions = await api.get('/cpo/sessions');
      const running = sessions.find(s => s.status === 'active' || s.status === 'upcoming') ?? null;
      setRunningSession(running);
    } catch { /* ignore — form still usable */ }
  }

  useEffect(() => {
    api.get('/cpo/me').then(setCpo).catch(() => {});
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
      setCloseError(err.message);
    } finally {
      setClosing(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    if (isAlreadyClosed(date, endTime, grace)) {
      setError('The end time (plus grace period) has already passed — please set a future end time.');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/cpo/sessions', {
        session_date: date,
        start_time: startTime,
        end_time: endTime,
        grace_period_minutes: grace,
      });
      navigate('/dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Open a new session</h1>
          <p className="page-subtitle">
            Pick a date and time window. Team members can order between start and end time.
          </p>
        </div>
        <button className="btn btn-ghost" onClick={() => navigate('/dashboard')}>✕ close</button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Running session banner — only shown when a session is active or upcoming */}
      {runningSession && (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 16, padding: '12px 16px', marginBottom: 20,
          background: 'var(--color-accent-soft)',
          border: '1px solid var(--color-accent)',
          borderRadius: 'var(--radius-md)',
        }}>
          <div>
            <span style={{ fontWeight: 600, color: 'var(--color-accent)' }}>
              A session is already {runningSession.status}.
            </span>
            {' '}
            <span className="text-soft text-sm">
              {runningSession.session_date} · {runningSession.start_time} — {runningSession.end_time}
            </span>
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
            {closing ? 'Closing…' : 'Close the running session'}
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ maxWidth: 560 }}>
        <div className="card card-pad" style={{ marginBottom: 16 }}>
          {/* Date + times */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
            <div className="form-group">
              <label className="form-label" htmlFor="sess-date">Date</label>
              <input
                id="sess-date" className="form-input" type="date" required
                value={date} onChange={e => setDate(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="sess-start">Start time</label>
              <input
                id="sess-start" className="form-input" type="time" required
                value={startTime} onChange={e => setStartTime(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="sess-end">End time</label>
              <input
                id="sess-end" className="form-input" type="time" required
                value={endTime} onChange={e => setEndTime(e.target.value)}
              />
            </div>
          </div>

          {/* Grace period stepper */}
          <div className="row" style={{ gap: 16, marginBottom: 16, alignItems: 'center' }}>
            <div className="form-group" style={{ flexShrink: 0 }}>
              <span className="form-label" style={{ display: 'block', marginBottom: 5 }}>Grace period</span>
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
                <span className="text-soft text-sm">min</span>
              </div>
            </div>
            {cutoff && (
              <p className="text-faint text-sm" style={{ marginTop: 18 }}>
                orders submitted up to <span className="mono">{cutoff}</span> still accepted
              </p>
            )}
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '4px 0 16px' }} />

          {/* Team link */}
          <div className="form-group">
            <label className="form-label" htmlFor="team-link">
              Team ordering link · stays the same for every session
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
                {copied ? '✓ copied' : '⧉ copy'}
              </button>
            </div>
          </div>
        </div>

        <div className="row" style={{ gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" className="btn" onClick={() => navigate('/dashboard')}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Opening…' : 'Open session'}
          </button>
        </div>
      </form>
    </div>
  );
}
