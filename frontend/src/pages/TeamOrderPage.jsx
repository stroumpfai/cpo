import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api.js';
import { parseUtcDt, utcHhmmToLocal } from '../utils/time.js';
import {
  clearMemberIdentity,
  getMemberIdentity,
  setMemberIdentity,
} from '../utils/memberIdentity.js';

// Deliberately looser than the server's email_validator: a client stricter than
// the server would block addresses the backend happily accepts.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function msToCountdown(ms) {
  const clamped = Math.max(0, ms);
  const mins    = Math.floor(clamped / 60_000);
  const secs    = Math.floor((clamped % 60_000) / 1_000);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

let _uid = 0;
function nextUid() { return ++_uid; }

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TeamOrderPage() {
  const { link } = useParams();

  const [sessionInfo, setSessionInfo] = useState(null);
  const [loading, setLoading]         = useState(true);
  const [fetchError, setFetchError]   = useState('');

  // Cart: [{uid, memberName, pizzaId, pizzaName, pizzaPrice, comment}]
  // Name and email are held separately so a mode flip never shows one as the other.
  const [name, setName]           = useState('');
  const [email, setEmail]         = useState('');
  const [prefilled, setPrefilled] = useState(false);
  const [pizzaId, setPizzaId]     = useState('');
  const [comment, setComment]     = useState('');
  const [cart, setCart]           = useState([]);
  const [cartError, setCartError] = useState('');

  // Submit
  const [submitting, setSubmitting]   = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitted, setSubmitted]     = useState(false);

  // Countdown to end_time (no grace)
  const [countdown, setCountdown] = useState('--:--');
  const timerRef = useRef(null);

  // ── Fetch & poll session status ──────────────────────────────────────────
  async function fetchStatus() {
    try {
      const data = await api.get(`/orders/${link}`);
      setSessionInfo(data);
    } catch (err) {
      setFetchError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 20_000);
    return () => clearInterval(id);
  }, [link]);   // eslint-disable-line react-hooks/exhaustive-deps

  // ── Prefill the identity remembered from a previous visit ────────────────
  useEffect(() => {
    const stored = getMemberIdentity(link);
    setName(stored.name);
    setEmail(stored.email);
    setPrefilled(Boolean(stored.name || stored.email));
  }, [link]);

  // Initialize pizza selector once pizzas load
  useEffect(() => {
    if (sessionInfo?.pizzas?.length && !pizzaId) {
      setPizzaId(sessionInfo.pizzas[0].id);
    }
  }, [sessionInfo?.pizzas?.length]);   // eslint-disable-line react-hooks/exhaustive-deps

  // ── Countdown ticker ─────────────────────────────────────────────────────
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (sessionInfo?.status !== 'active' || !sessionInfo.session_date || !sessionInfo.end_time) return;

    const endMs = parseUtcDt(sessionInfo.session_date, sessionInfo.end_time);
    function tick() { setCountdown(msToCountdown(endMs - Date.now())); }
    tick();
    timerRef.current = setInterval(tick, 1_000);
    return () => clearInterval(timerRef.current);
  }, [sessionInfo?.status, sessionInfo?.session_date, sessionInfo?.end_time]);

  // ── Identity mode (driven by the CPO's setting) ──────────────────────────
  const emailMode  = sessionInfo?.member_identifier === 'email';
  const idValue    = emailMode ? email : name;
  const setIdValue = emailMode ? setEmail : setName;
  const idField    = emailMode ? 'email' : 'name';
  // Name mode keeps id="order-name" so existing selectors stay valid.
  const idInputId  = emailMode ? 'order-email' : 'order-name';

  // ── Cart actions ─────────────────────────────────────────────────────────
  function addToCart() {
    const value = idValue.trim();
    if (!value) {
      setCartError(emailMode ? 'Enter an email first.' : 'Enter a name first.');
      return;
    }
    if (emailMode && !EMAIL_RE.test(value)) {
      setCartError('Enter a valid email address.');
      return;
    }
    if (!pizzaId) { setCartError('Select a plate.'); return; }
    const pizza = sessionInfo.pizzas.find(p => p.id === pizzaId);
    if (!pizza) return;
    setCart(c => [...c, { uid: nextUid(), memberName: value, pizzaId: pizza.id, pizzaName: pizza.name, pizzaPrice: pizza.price, comment: comment.trim() || null }]);
    setCartError('');
    // The identity stays put — adding a second plate shouldn't mean retyping it.
    setIdValue(value);
    setComment('');
    setPizzaId(sessionInfo.pizzas[0]?.id ?? '');
  }

  function removeFromCart(uid) {
    setCart(c => c.filter(i => i.uid !== uid));
  }

  function clearCart() {
    setCart([]);
    setCartError('');
    setSubmitError('');
  }

  // ── Submit ───────────────────────────────────────────────────────────────
  async function submitOrder() {
    if (cart.length === 0) { setCartError('Add at least one plate before submitting.'); return; }
    // The server consumes the rate-limit slot before validating, so letting a
    // guaranteed-400 through would also cost the user a 5-second lockout.
    if (emailMode && cart.some(i => !EMAIL_RE.test(i.memberName))) {
      setCartError('Some entries are no longer valid email addresses. Remove and re-add them.');
      return;
    }
    setSubmitError('');
    setSubmitting(true);
    try {
      await api.post(`/orders/${link}/submit`, {
        items: cart.map(i => ({ member_name: i.memberName, pizza_id: i.pizzaId, comment: i.comment })),
      });
      // Only remember values that actually made it through — not typos.
      setMemberIdentity(link, idField, idValue.trim());
      setPrefilled(true);
      setSubmitted(true);
    } catch (err) {
      if (err.status === 429) {
        setSubmitError('Too many orders. Please wait 5 seconds before trying again.');
      } else if (err.status === 403) {
        setSubmitError('Session is closed — no more orders accepted.');
        fetchStatus();
      } else {
        setSubmitError(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleAddAnother() {
    setSubmitted(false);
    clearCart();
    setComment('');
    setPizzaId(sessionInfo?.pizzas[0]?.id ?? '');
  }

  function forgetIdentity() {
    clearMemberIdentity(link);
    setName('');
    setEmail('');
    setPrefilled(false);
    setCartError('');
  }

  // ── Shared header bar ────────────────────────────────────────────────────
  const teamName = sessionInfo?.team_name ?? '';

  const headerBar = (showLive) => (
    <header style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '14px 24px',
      background: 'var(--color-bg)',
      borderBottom: '1px solid var(--color-border)',
      position: 'sticky', top: 0, zIndex: 10,
    }}>
      <span style={{ fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>
        🍕 {teamName} · order day
      </span>
      {showLive && (
        <span className="chip chip-live" style={{ fontSize: 'var(--font-size-sm)', gap: 6 }}>
          <span className="pulse-dot" />
          live · closes {utcHhmmToLocal(sessionInfo.session_date, sessionInfo.end_time)} (in {countdown})
        </span>
      )}
    </header>
  );

  // ── Render ───────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span className="text-soft">Loading…</span>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div className="alert alert-error">{fetchError}</div>
      </div>
    );
  }

  // Session closed or upcoming
  if (sessionInfo?.status !== 'active') {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--color-surface)' }}>
        {headerBar(false)}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', minHeight: 'calc(100vh - 56px)',
          padding: 40, textAlign: 'center', gap: 12,
        }}>
          <div style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700, color: 'var(--color-accent)' }}>
            Session is closed.
          </div>
          <div className="text-soft">No more orders for today.</div>
        </div>
      </div>
    );
  }

  // Success state
  if (submitted) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--color-surface)' }}>
        {headerBar(false)}
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 24px' }}>
          <div className="card card-pad" style={{
            maxWidth: 520, width: '100%', textAlign: 'center',
            display: 'flex', flexDirection: 'column', gap: 12,
          }}>
            <div style={{ fontSize: 72, color: 'var(--color-accent)', lineHeight: 1 }}>✓</div>
            <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 700 }}>Order placed!</h1>
            <p className="text-soft">
              {cart.length} {cart.length === 1 ? 'plate' : 'plates'} heading to the CPO.
            </p>
            <p className="text-faint text-sm">
              Orders can't be edited after submission. Contact your CPO if you change your mind.
            </p>
            <div style={{ marginTop: 8 }}>
              <button className="btn" onClick={handleAddAnother}>add another order</button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Active session — order form
  const pizzas    = sessionInfo.pizzas ?? [];
  const cartTotal = cart.reduce((s, i) => s + i.pizzaPrice, 0);
  // Emails need far more room than first names.
  const personColWidth = emailMode ? 180 : 90;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-surface)', display: 'flex', flexDirection: 'column' }}>
      {headerBar(true)}

      <div style={{ flex: 1, padding: 24, maxWidth: 900, margin: '0 auto', width: '100%' }}>
        {submitError && (
          <div className="alert alert-error" style={{ marginBottom: 16 }}>{submitError}</div>
        )}

        <div className="order-grid">
          {/* ── Left: add-to-cart form ── */}
          <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>Add a plate for a person</h2>

            <div className="form-group">
              <label className="form-label" htmlFor={idInputId}>
                {emailMode ? 'Your email' : 'Your name'}
              </label>
              <input
                id={idInputId} className="form-input"
                type={emailMode ? 'email' : 'text'}
                inputMode={emailMode ? 'email' : 'text'}
                autoComplete={emailMode ? 'email' : 'name'}
                maxLength={emailMode ? 254 : 100}
                placeholder={emailMode ? 'e.g. alice@example.com' : 'e.g. Alice'}
                value={idValue}
                onChange={e => { setIdValue(e.target.value); setCartError(''); }}
              />
              {prefilled && idValue && (
                <button
                  type="button"
                  className="btn btn-ghost text-xs"
                  style={{ marginTop: 4, padding: '2px 0', color: 'var(--color-text-faint)' }}
                  onClick={forgetIdentity}
                >
                  not you? clear
                </button>
              )}
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="order-pizza">Pick a plate</label>
              {pizzas.length === 0 ? (
                <p className="text-faint text-sm">No plates on the menu yet.</p>
              ) : (
                <select
                  id="order-pizza" className="form-input"
                  value={pizzaId}
                  onChange={e => { setPizzaId(e.target.value); setCartError(''); }}
                >
                  {pizzas.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.name} — {sessionInfo.currency} {p.price.toFixed(2)}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="order-comment">
                Comment / Extra <span className="text-faint">(optional)</span>
              </label>
              <input
                id="order-comment"
                className="form-input"
                placeholder="e.g. no olives, extra cheese"
                maxLength={100}
                value={comment}
                onChange={e => setComment(e.target.value)}
              />
            </div>

            <div className="text-sm text-soft">
              Restaurant menu:{' '}
              {sessionInfo.pizzeria_url ? (
                <a
                  href={sessionInfo.pizzeria_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  view online
                </a>
              ) : (
                <span>—</span>
              )}
            </div>

            {cartError && <div className="alert alert-error text-sm">{cartError}</div>}

            <button
              className="btn btn-primary btn-full"
              onClick={addToCart}
              disabled={pizzas.length === 0}
            >
              add to your order
            </button>
          </div>

          {/* ── Right: cart ── */}
          <div className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 600 }}>Overview of your order</h2>

            {cart.length === 0 ? (
              <p className="text-faint text-sm">Nothing added yet.</p>
            ) : (
              <>
                <div className="row" style={{
                  borderBottom: '1px solid var(--color-border)', paddingBottom: 6,
                  fontSize: 'var(--font-size-xs)', color: 'var(--color-text-faint)',
                  textTransform: 'uppercase', letterSpacing: '.06em',
                }}>
                  <span style={{ flex: 1 }}>Plate</span>
                  <span style={{ width: personColWidth }}>Person</span>
                  <span style={{ width: 80, textAlign: 'right' }}>{sessionInfo.currency}</span>
                  <span style={{ width: 24 }} />
                </div>

                {cart.map(item => (
                  <div key={item.uid} className="row" style={{
                    borderBottom: '1px dashed var(--color-border)',
                    paddingBottom: 8, alignItems: 'center',
                  }}>
                    <span style={{ flex: 1 }}>
                      {item.pizzaName}
                      {item.comment && (
                        <span className="order-comment">{item.comment}</span>
                      )}
                    </span>
                    <span
                      className="text-soft"
                      style={{ width: personColWidth, fontSize: 'var(--font-size-sm)', overflowWrap: 'anywhere' }}
                      title={item.memberName}
                    >
                      {item.memberName}
                    </span>
                    <span className="mono" style={{ width: 80, textAlign: 'right' }}>
                      {item.pizzaPrice.toFixed(2)}
                    </span>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 24, padding: 0, color: 'var(--color-accent)', justifyContent: 'center' }}
                      onClick={() => removeFromCart(item.uid)}
                      title="Remove"
                    >✕</button>
                  </div>
                ))}

                <div className="row" style={{ marginTop: 4 }}>
                  <span style={{ marginLeft: 'auto', fontWeight: 700, fontSize: 'var(--font-size-lg)' }}>
                    {sessionInfo.currency} {cartTotal.toFixed(2)}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Disclaimer + actions */}
        <p className="text-faint text-sm" style={{ textAlign: 'center', margin: '20px 0 12px' }}>
          Heads up: orders can't be edited after submission — contact your CPO if you change your mind.
        </p>
        <div className="row" style={{ justifyContent: 'flex-end', gap: 10 }}>
          <button className="btn" onClick={clearCart} disabled={cart.length === 0}>cancel</button>
          <button
            className="btn btn-primary"
            onClick={submitOrder}
            disabled={submitting || cart.length === 0}
          >
            {submitting ? 'Submitting…' : 'submit order ✓'}
          </button>
        </div>
      </div>
    </div>
  );
}
