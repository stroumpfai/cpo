import { useState } from 'react';

function fmtDate(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short',
  });
}

export function SessionHeader({ session, uniqueLink, onRefresh, onPrint }) {
  const [copied, setCopied] = useState(false);

  function copyLink() {
    const url = `${window.location.origin}/orders/${uniqueLink}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const [endH, endM] = session.end_time.split(':').map(Number);
  const graceM = session.grace_period_minutes ?? 2;
  const closeMin = endM + graceM;
  const closeH   = endH + Math.floor(closeMin / 60);
  const closeFmt = `${String(closeH % 24).padStart(2, '0')}:${String(closeMin % 60).padStart(2, '0')}`;

  return (
    <div className="page-header" style={{ alignItems: 'flex-start', marginBottom: 20 }}>
      <div>
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">
          Session — {fmtDate(session.session_date)}
          &nbsp;·&nbsp;
          {session.start_time} — {closeFmt}
          &nbsp;
          <span className="text-faint">(ordering window incl. {graceM}′ grace)</span>
        </p>
      </div>
      <div className="row" style={{ gap: 8, flexShrink: 0 }}>
        <button className="btn" onClick={onRefresh} title="Refresh">↻ refresh</button>
        <button className="btn btn-ghost" onClick={onPrint} title="Print">⎙ print</button>
        <button
          className="btn btn-primary"
          onClick={copyLink}
          title="Copy team ordering link"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--font-size-xs)' }}
        >
          {copied ? '✓ copied' : `🔗 /orders/${uniqueLink}`}
        </button>
      </div>
    </div>
  );
}
