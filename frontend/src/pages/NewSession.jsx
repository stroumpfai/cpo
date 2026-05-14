import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';

function today() {
  return new Date().toISOString().slice(0, 10);
}

function computeCutoff(endTime, graceMins) {
  if (!endTime) return '';
  const [h, m] = endTime.split(':').map(Number);
  const total  = h * 60 + m + graceMins;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

export function NewSession() {
  const [date, setDate]           = useState(today());
  const [startTime, setStartTime] = useState('11:30');
  const [endTime, setEndTime]     = useState('12:00');
  const [grace, setGrace]         = useState(2);
  const [cpo, setCpo]             = useState(null);
  const [error, setError]         = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied]       = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/cpo/me').then(setCpo).catch(() => {});
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

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
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
