import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { parseUtcDt } from '../utils/time.js';
import { SessionHeader } from '../components/SessionHeader.jsx';
import { StatCards } from '../components/StatCards.jsx';
import { OrdersPerPersonTable } from '../components/OrdersPerPersonTable.jsx';
import { PizzeriaSummaryTable } from '../components/PizzeriaSummaryTable.jsx';

function msToCountdown(ms) {
  const total = Math.max(0, ms);
  const mins  = Math.floor(total / 60_000);
  const secs  = Math.floor((total % 60_000) / 1_000);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function bestSession(sessions) {
  return (
    sessions.find(s => s.status === 'active')   ||
    sessions.find(s => s.status === 'upcoming') ||
    sessions[sessions.length - 1]               ||
    null
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CPODashboard() {
  const [cpo, setCpo]               = useState(null);
  const [session, setSession]       = useState(null);   // best session object
  const [summary, setSummary]       = useState(null);
  const [activeTab, setActiveTab]   = useState('distribution');
  const [countdown, setCountdown]   = useState('--:--');
  const [countdownPct, setCountdownPct] = useState(100);
  const [paidSet, setPaidSet]       = useState(new Set());
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [emailsCopied, setEmailsCopied] = useState(false);
  const esRef       = useRef(null);
  const inFlightRef = useRef(new Set());

  // ── Initial load ────────────────────────────────────────────────────────
  useEffect(() => {
    async function load() {
      try {
        const [me, sessions] = await Promise.all([
          api.get('/cpo/me'),
          api.get('/cpo/sessions'),
        ]);
        setCpo(me);
        const best = bestSession(sessions);
        setSession(best);
        if (best) {
          const summaryData = await api.get(`/cpo/sessions/${best.id}/summary`);
          setSummary(summaryData);
          reconcilePaidSet(summaryData.distribution);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // ── SSE connection ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!session || session.status === 'closed') return;

    const sessionId = session.id;
    let es = null;
    let cancelled = false;

    function onUpdate(e) {
      const data = JSON.parse(e.data);
      setSummary(data);
      reconcilePaidSet(data.distribution);
    }

    function onSessionClosed(e) {
      const data = JSON.parse(e.data);
      setSummary(data);
      reconcilePaidSet(data.distribution);
      setSession(prev => ({ ...prev, status: 'closed' }));
      es.close();
    }

    async function connect() {
      if (cancelled) return;
      try {
        const { sse_token } = await api.post(`/cpo/sessions/${sessionId}/sse-token`, {});
        if (cancelled) return;
        const url = `/api/cpo/sessions/${sessionId}/summary/sse?token=${encodeURIComponent(sse_token)}`;
        es = new EventSource(url);
        esRef.current = es;
        es.addEventListener('update', onUpdate);
        es.addEventListener('session_closed', onSessionClosed);
        es.onerror = onSseError;
      } catch {
        // POST for SSE token failed (session gone, auth expired) — don't retry
      }
    }

    function onSseError() {
      if (cancelled) return;
      es.close();
      esRef.current = null;
      setTimeout(connect, 2000);
    }

    connect();
    return () => {
      cancelled = true;
      es?.close();
      esRef.current = null;
    };
  }, [session?.id]);

  // ── Countdown timer ──────────────────────────────────────────────────────
  useEffect(() => {
    if (session?.status !== 'active') return;

    const startMs = parseUtcDt(session.session_date, session.start_time);
    const endMs   = parseUtcDt(session.session_date, session.end_time);
    const closeMs = endMs + (session.grace_period_minutes ?? 2) * 60_000;
    const totalMs = closeMs - startMs;

    function tick() {
      const now       = Date.now();
      const remaining = closeMs - now;
      const elapsed   = now - startMs;
      setCountdown(msToCountdown(remaining));
      setCountdownPct(Math.max(0, Math.min(100, (1 - elapsed / totalMs) * 100)));
    }

    tick();
    const id = setInterval(tick, 1_000);
    return () => clearInterval(id);
  }, [session?.id, session?.status]);

  // ── Actions ──────────────────────────────────────────────────────────────
  function copyEmails(list) {
    navigator.clipboard.writeText(list.join(', ')).then(() => {
      setEmailsCopied(true);
      setTimeout(() => setEmailsCopied(false), 2000);
    });
  }

  async function refresh() {
    if (!session) return;
    try {
      setSummary(await api.get(`/cpo/sessions/${session.id}/summary`));
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteOrder(orderId) {
    try {
      await api.delete(`/cpo/orders/${orderId}`);
      setSummary(prev => {
        const distribution = prev.distribution.filter(r => r.order_id !== orderId);
        const totalPrice   = distribution.reduce((s, r) => s + r.price, 0);
        return { ...prev, distribution, total_orders: distribution.length, total_price: totalPrice };
      });
    } catch { /* ignore — SSE will sync on next event */ }
  }

  function reconcilePaidSet(distribution) {
    setPaidSet(prev => {
      const next = new Set(prev);
      for (const row of distribution) {
        if (!inFlightRef.current.has(row.order_id)) {
          row.received ? next.add(row.order_id) : next.delete(row.order_id);
        }
      }
      return next;
    });
  }

  async function togglePaid(orderId) {
    const nextReceived = !paidSet.has(orderId);
    inFlightRef.current.add(orderId);
    setPaidSet(prev => {
      const next = new Set(prev);
      nextReceived ? next.add(orderId) : next.delete(orderId);
      return next;
    });
    try {
      await api.patch(`/cpo/orders/${orderId}/received`, { received: nextReceived });
    } catch {
      setPaidSet(prev => {
        const next = new Set(prev);
        nextReceived ? next.delete(orderId) : next.add(orderId);
        return next;
      });
    } finally {
      inFlightRef.current.delete(orderId);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────
  if (loading) return <div className="text-soft text-sm">Loading…</div>;
  if (error)   return <div className="alert alert-error">{error}</div>;

  if (!session) {
    return (
      <div>
        <div className="page-header" style={{ marginBottom: 16 }}>
          <h1 className="page-title">Dashboard</h1>
        </div>
        <div className="card card-pad">
          <p className="text-soft" style={{ marginBottom: 12 }}>No sessions yet.</p>
          <Link to="/dashboard/new-session" className="btn btn-primary">
            Open a new session
          </Link>
        </div>
      </div>
    );
  }

  const isClosed     = (summary?.status ?? session.status) === 'closed';
  const isUpcoming   = (summary?.status ?? session.status) === 'upcoming';
  const memberCount  = new Set((summary?.distribution ?? []).map(r => r.member_name)).size;

  // In email mode the member column holds addresses — offer them as one
  // paste-ready list so the CPO can announce the delivery by mail.
  // Exact-match dedup is enough: the server lower-cases every stored address.
  const emails = cpo?.member_identifier === 'email'
    ? [...new Set((summary?.distribution ?? []).map(r => r.member_name))]
    : [];

  return (
    <div>
      <SessionHeader
        session={session}
        uniqueLink={cpo?.unique_link}
        onRefresh={refresh}
        onPrint={() => globalThis.print()}
      />

      {isClosed && (
        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          This session is closed. The summary below is final.
        </div>
      )}
      {isUpcoming && (
        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          Session hasn't started yet — opens at {session.start_time}.
        </div>
      )}

      <StatCards
        memberCount={memberCount}
        pizzaCount={summary?.total_orders ?? 0}
        totalPrice={summary?.total_price ?? 0}
        countdown={countdown}
        countdownPct={countdownPct}
        isClosed={isClosed}
        currency={cpo?.currency ?? 'CHF'}
      />

      {/* Tab bar — hidden in print */}
      <div className="tabs no-print">
        <button
          className={`tab${activeTab === 'distribution' ? ' active' : ''}`}
          onClick={() => setActiveTab('distribution')}
        >
          Orders per person
        </button>
        <button
          className={`tab${activeTab === 'pizzeria' ? ' active' : ''}`}
          onClick={() => setActiveTab('pizzeria')}
        >
          List for ordering at Restaurant
        </button>
        {emails.length > 0 && (
          <button
            className="btn btn-ghost"
            style={{ marginLeft: 'auto' }}
            onClick={() => copyEmails(emails)}
            title="Copy every member's email, ready to paste into your mail client"
          >
            {emailsCopied ? '✓ copied' : `copy emails (${emails.length})`}
          </button>
        )}
      </div>

      {/* Tab content — hidden in print */}
      <div className="no-print">
        {activeTab === 'distribution' ? (
          <OrdersPerPersonTable
            rows={summary?.distribution ?? []}
            paidSet={paidSet}
            onTogglePaid={togglePaid}
            onDelete={deleteOrder}
            isClosed={isClosed}
            currency={cpo?.currency ?? 'CHF'}
          />
        ) : (
          <PizzeriaSummaryTable
            rows={summary?.pizzeria ?? []}
            totalOrders={summary?.total_orders ?? 0}
            totalPrice={summary?.total_price ?? 0}
            currency={cpo?.currency ?? 'CHF'}
          />
        )}
      </div>

      {/* Print-only: both tables stacked with section headings */}
      <div className="print-only">
        <h2 className="print-section-title">Orders per person</h2>
        <OrdersPerPersonTable
          rows={summary?.distribution ?? []}
          paidSet={paidSet}
          onTogglePaid={togglePaid}
          onDelete={deleteOrder}
          isClosed={isClosed}
          printMode
          currency={cpo?.currency ?? 'CHF'}
        />
        <h2 className="print-section-title">Order at restaurant</h2>
        <PizzeriaSummaryTable
          rows={summary?.pizzeria ?? []}
          totalOrders={summary?.total_orders ?? 0}
          totalPrice={summary?.total_price ?? 0}
          currency={cpo?.currency ?? 'CHF'}
        />
      </div>
    </div>
  );
}
