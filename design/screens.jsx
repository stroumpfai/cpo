/* global React */
const { Fragment } = React;

/* ---------- shared atoms ---------- */
const Ph = ({ label, h = 60, style }) =>
<div className="ph" style={{ height: h, ...style }}>{label}</div>;

const Field = ({ label, value, w, tone }) =>
<div className="field" style={{ width: w }}>
    {label && <span className="lbl" style={{ marginRight: 8 }}>{label}</span>}
    <span style={{ color: tone || 'var(--ink)' }}>{value}</span>
  </div>;

const Btn = ({ children, kind = '', style }) =>
<span className={`btn ${kind}`} style={style}>{children}</span>;

const Eyebrow = ({ children }) => <div className="eyebrow">{children}</div>;
const H1 = ({ children, style }) => <div className="h1" style={style}>{children}</div>;
const H2 = ({ children, style }) => <div className="h2" style={style}>{children}</div>;
const Sq = () => <div className="squiggle" />;

/* annotation arrow + note */
const Note = ({ x, y, w = 180, children, dir = 'left' }) =>
<div className="annot" style={{ left: x, top: y, width: w, textAlign: dir }}>
    {children}
  </div>;


/* ================================================================ *
 * DIRECTION 1 — CLASSIC ADMIN DASHBOARD
 * "Looks like a normal SaaS dashboard. Sidebar + tabs + tables."
 * ================================================================ */

const D1_CPOHome = () =>
<div className="wf" style={{ display: 'flex', gap: 14, padding: 18 }}>
    {/* sidebar */}
    <div style={{ width: 170, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="h2" style={{ marginBottom: 4 }}>🍕 CPO</div>
      <div className="eyebrow">team · engineering</div>
      <div style={{ height: 10 }} />
      {['Dashboard', 'Open a new sessions', 'List of Pizzas', 'Settings'].map((s, i) =>
    <div key={s} className={`field ${i === 0 ? 'tone' : ''}`} style={{ borderStyle: i === 0 ? 'solid' : 'dashed', fontWeight: i === 0 ? 700 : 400, color: i === 0 ? 'var(--ink)' : 'var(--ink-soft)' }}>
          {s}
        </div>
    )}
      <div style={{ flex: 1 }} />
      <div className="chip tone">JD · log out</div>
    </div>

    {/* main */}
    <div className="grow" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <H1>Dashboard</H1>
          <div className="soft" style={{ fontSize: 13, marginTop: 4 }}>Session — Fri 14 May · 11:30 — 12:02 · ordering window (incl. 2’ grace)</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Btn>↻refresh</Btn>
          <Btn kind="ghost">⎙print</Btn>
          <Btn kind="accent" style={{ padding: '8px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 13 }}>
            🔗orders.app/x7k9mP2qRvL5j&nbsp;
          </Btn>
        </div>
      </div>

      {/* stat row — each "order" = one pizza row now */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
        {[
      ['members', '9'],
      ['pizzas', '22'],
      ['CHF total', '289.00']].
      map(([k, v]) =>
      <div key={k} className="box tone" style={{ padding: '10px 12px' }}>
            <div className="eyebrow">{k}</div>
            <div className="num-big" style={{ fontSize: 32 }}>{v}</div>
          </div>
      )}
        {/* countdown card — special: live indicator, clock, accent digits */}
        <div className="box" style={{ padding: '10px 12px', borderColor: 'var(--accent)', background: 'var(--accent-soft)', position: 'relative' }}>
          <div className="row" style={{ alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 14, lineHeight: 1 }} aria-hidden="true">⏱</span>
            <span className="eyebrow" style={{ color: 'var(--accent)' }}>ends in</span>
            <span style={{ flex: 1 }} />
            <span className="chip accent" style={{ fontSize: 9, padding: '0 6px', gap: 3 }}>
              <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#fff', animation: 'pulse 1.2s ease-in-out infinite' }} />
              live
            </span>
          </div>
          <div className="num-big mono" style={{ color: 'var(--accent)', letterSpacing: '-0.02em', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, fontSize: 36 }}>
            06:42
          </div>
          <div className="mono faint" style={{ fontSize: 10, marginTop: -4 }}>min : sec</div>
          {/* progress bar showing how much of the window is left */}
          <div style={{ height: 4, background: '#fff', border: '1.5px solid var(--ink)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
            <div style={{ width: '22%', height: '100%', background: 'var(--accent)' }} />
          </div>
        </div>
      </div>

      {/* tabs */}
      <div style={{ display: 'flex', gap: 18, marginTop: 4 }}>
        <div className="pill-tab on">Orders per person</div>
        <div className="pill-tab">List for ordering at Pizzeria</div>
      </div>

      <div className="box thin" style={{ padding: 12, flex: 1 }}>
        <table className="sketch">
          <thead><tr>
            <th>time ↓</th><th>member</th><th>client ip</th><th>pizza</th><th>price (CHF)</th><th>action</th>
          </tr></thead>
          <tbody>
            {[
          ['11:36:42', 'Alice', '192.168.1.21', 'Margherita', '12.50', true],
          ['11:36:42', 'Alice', '192.168.1.21', 'Diavola', '14.50'],
          ['11:36:42', 'Alice', '192.168.1.21', 'Marinara', '10.00', true],
          ['11:36:18', 'Bob', '192.168.1.21', 'Diavola', '14.50'],
          ['11:35:55', 'Chen', '10.0.0.4', 'Quattro Stagioni', '15.00'],
          ['11:35:14', 'Dani', '192.168.1.34', 'Margherita', '12.50'],
          ['11:34:48', 'Eli', '192.168.1.21', 'Capricciosa', '15.50'],
          ['11:34:02', 'Finn', '192.168.1.7', 'Marinara', '10.00']].
          map((r, i) =>
          <tr key={i}>
                <td className="num faint">{r[0]}</td>
                <td>{r[1]}</td>
                <td className="num faint">{r[2]}</td>
                <td>{r[3]}</td>
                <td className="num">{r[4]}</td>
                <td><span className="tag-x">{r[5] ? '✓' : '💰'} received · ✕ delete</span></td>
              </tr>
          )}
          </tbody>
        </table>
      </div>
    </div>
  </div>;


/* ============== same dashboard, pizzeria tab active ============== */
const D1_CPOHomePizzeria = () =>
<div className="wf" style={{ display: 'flex', gap: 14, padding: 18 }}>
    {/* sidebar */}
    <div style={{ width: 170, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="h2" style={{ marginBottom: 4 }}>🍕 CPO</div>
      <div className="eyebrow">team · engineering</div>
      <div style={{ height: 10 }} />
      {['Dashboard', 'Open a new sessions', 'List of Pizzas', 'Settings'].map((s, i) =>
    <div key={s} className={`field ${i === 0 ? 'tone' : ''}`} style={{ borderStyle: i === 0 ? 'solid' : 'dashed', fontWeight: i === 0 ? 700 : 400, color: i === 0 ? 'var(--ink)' : 'var(--ink-soft)' }}>
          {s}
        </div>
    )}
      <div style={{ flex: 1 }} />
      <div className="chip tone">JD · log out</div>
    </div>

    {/* main */}
    <div className="grow" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div>
          <H1>Dashboard</H1>
          <div className="soft" style={{ fontSize: 13, marginTop: 4 }}>Session — Fri 14 May · 11:30 — 12:02 · ordering window (incl. 2’ grace)</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Btn>↻refresh</Btn>
          <Btn kind="ghost">⎙print</Btn>
          <Btn kind="accent" style={{ padding: '8px 14px', fontFamily: 'JetBrains Mono, monospace', fontSize: 13 }}>
            🔗orders.app/x7k9mP2qRvL5j&nbsp;
          </Btn>
        </div>
      </div>

      {/* stat row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
        {[
      ['members', '9'],
      ['pizzas', '22'],
      ['CHF total', '289.00']].
      map(([k, v]) =>
      <div key={k} className="box tone" style={{ padding: '10px 12px' }}>
            <div className="eyebrow">{k}</div>
            <div className="num-big" style={{ fontSize: 32 }}>{v}</div>
          </div>
      )}
        <div className="box" style={{ padding: '10px 12px', borderColor: 'var(--accent)', background: 'var(--accent-soft)', position: 'relative' }}>
          <div className="row" style={{ alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 14, lineHeight: 1 }} aria-hidden="true">⏱</span>
            <span className="eyebrow" style={{ color: 'var(--accent)' }}>ends in</span>
            <span style={{ flex: 1 }} />
            <span className="chip accent" style={{ fontSize: 9, padding: '0 6px', gap: 3 }}>
              <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#fff', animation: 'pulse 1.2s ease-in-out infinite' }} />
              live
            </span>
          </div>
          <div className="num-big mono" style={{ color: 'var(--accent)', letterSpacing: '-0.02em', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700, fontSize: 36 }}>
            06:42
          </div>
          <div className="mono faint" style={{ fontSize: 10, marginTop: -4 }}>min : sec</div>
          <div style={{ height: 4, background: '#fff', border: '1.5px solid var(--ink)', borderRadius: 2, marginTop: 6, overflow: 'hidden' }}>
            <div style={{ width: '22%', height: '100%', background: 'var(--accent)' }} />
          </div>
        </div>
      </div>

      {/* tabs — pizzeria tab active */}
      <div style={{ display: 'flex', gap: 18, marginTop: 4 }}>
        <div className="pill-tab">Orders per person</div>
        <div className="pill-tab on">List for ordering at Pizzeria</div>
      </div>

      <div className="box thin" style={{ padding: 12, flex: 1 }}>
        <table className="sketch">
          <thead><tr>
            <th>pizza</th><th>count</th><th>total (CHF)</th>
          </tr></thead>
          <tbody>
            {[
          ['Margherita', 8, '100.00'],
          ['Diavola', 5, '72.50'],
          ['Marinara', 4, '40.00'],
          ['Capricciosa', 3, '46.50'],
          ['Quattro Stagioni', 2, '30.00']].
          map(([n, q, t]) =>
          <tr key={n}>
                <td>{n}</td>
                <td className="num">
                  <div className="row" style={{ alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 22, textAlign: 'right' }}>{q}</span>
                    <div style={{ width: `${q / 8 * 180}px`, height: 10, background: 'var(--accent)', border: '1.5px solid var(--ink)', borderRadius: 5 }} />
                  </div>
                </td>
                <td className="num">{t}</td>
              </tr>
          )}
            <tr>
              <td><b>total</b></td>
              <td className="num"><b>22</b></td>
              <td className="num"><b>289.00</b></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>;


const D1_TeamOrder = () =>
<div className="wf" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 24 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <div className="h2">🍕 Engineering · pizza day</div>
      <div className="chip accent">● live · closes 12:00 (in 06:42)</div>
    </div>
    <Sq />

    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18, alignItems: 'flex-start' }}>
      {/* LEFT — add to order */}
      <div className="box shadow" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <H2>Add a pizza for a person</H2>
        <div>
          <div className="eyebrow">your name</div>
          <Field value="Alice ____________________" />
        </div>
        <div>
          <div className="eyebrow">pick a pizza</div>
          <Field value="▾ Margherita — CHF 12.50" />
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
          <Btn kind="accent">add to your order</Btn>
        </div>
      </div>

      {/* RIGHT — running cart */}
      <div className="box" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <H2>Overview of your order</H2>
        </div>
        {/* column headers */}
        <div className="row" style={{ borderBottom: '1.5px solid var(--ink)', paddingBottom: 4 }}>
          <span className="eyebrow" style={{ width: 90 }}>name</span>
          <span className="eyebrow grow">pizza</span>
          <span className="eyebrow" style={{ width: 90, textAlign: 'right' }}>price (CHF)</span>
          <span style={{ width: 14 }} />
        </div>
        {[
      ['Alice', 'Margherita', '12.50'],
      ['Alice', 'Diavola', '14.50'],
      ['Bob', 'Marinara', '10.00']].
      map(([who, n, p], i) =>
      <div key={i} className="row" style={{ alignItems: 'center', borderBottom: '1.5px dashed var(--ink-faint)', paddingBottom: 4 }}>
            <span style={{ width: 90 }}>{who}</span>
            <span className="grow">{n}</span>
            <span className="mono" style={{ width: 90, textAlign: 'right' }}>{p}</span>
            <span className="tag-x" style={{ marginLeft: 8 }}>✕</span>
          </div>
      )}
        <hr className="sketch" />
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span className="eyebrow">total</span>
          <span className="num-big" style={{ fontSize: 32 }}>CHF 37.00</span>
        </div>
      </div>
    </div>

    <div className="soft" style={{ fontSize: 13, textAlign: 'center' }}>
      Heads up: orders can't be edited after submission — contact your CPO if you change your mind.
    </div>

    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
      <Btn>cancel</Btn>
      <Btn kind="accent">submit order ✓</Btn>
    </div>
  </div>;


const D1_Menu = () =>
<div className="wf" style={{ display: 'flex', gap: 14, padding: 18 }}>
    {/* sidebar — List of Pizzas active */}
    <div style={{ width: 170, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="h2" style={{ marginBottom: 4 }}>🍕 CPO</div>
      <div className="eyebrow">team · engineering</div>
      <div style={{ height: 10 }} />
      {['Dashboard', 'Open a new sessions', 'List of Pizzas', 'Settings'].map((s, i) =>
    <div key={s} className={`field ${i === 2 ? 'tone' : ''}`} style={{ borderStyle: i === 2 ? 'solid' : 'dashed', fontWeight: i === 2 ? 700 : 400, color: i === 2 ? 'var(--ink)' : 'var(--ink-soft)' }}>
          {s}
        </div>
    )}
      <div style={{ flex: 1 }} />
      <div className="chip tone">JD · log out</div>
    </div>

    {/* main content */}
    <div className="grow" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <H1>List of Pizzas</H1>
        <div className="soft">Your menu persists across sessions.</div>
      </div>
      <div className="box thin" style={{ padding: 12 }}>
        <table className="sketch">
          <thead><tr><th>pizza name</th><th>price (CHF)</th><th>actions</th></tr></thead>
          <tbody>
            {[
          ['Margherita', '12.50'],
          ['Diavola', '14.50'],
          ['Marinara', '10.00'],
          ['Quattro Stagioni', '15.00'],
          ['Capricciosa', '15.50']].
          map(([n, p]) =>
          <tr key={n}>
                <td>{n}</td>
                <td className="num">{p}</td>
                <td><span className="tag-x">✎ edit · ✕ delete</span></td>
              </tr>
          )}
            <tr>
              <td><Field value="type pizza name…" tone="var(--ink-faint)" /></td>
              <td><Field value="0.00" tone="var(--ink-faint)" /></td>
              <td><Btn>add</Btn></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>;


/* ============== new session — open ordering window ============== */
const D1_NewSession = () =>
<div className="wf" style={{ display: 'flex', gap: 14, padding: 18 }}>
    {/* sidebar — same as dashboard, different active item */}
    <div style={{ width: 170, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div className="h2" style={{ marginBottom: 4 }}>🍕 CPO</div>
      <div className="eyebrow">team · engineering</div>
      <div style={{ height: 10 }} />
      {['Dashboard', 'Open a new sessions', 'List of Pizzas', 'Settings'].map((s, i) =>
    <div key={s} className={`field ${i === 1 ? 'tone' : ''}`} style={{ borderStyle: i === 1 ? 'solid' : 'dashed', fontWeight: i === 1 ? 700 : 400, color: i === 1 ? 'var(--ink)' : 'var(--ink-soft)' }}>
          {s}
        </div>
    )}
      <div style={{ flex: 1 }} />
      <div className="chip tone">JD · log out</div>
    </div>

    {/* main content */}
    <div className="grow" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <H1>Open a new session</H1>
        <div className="soft">Pick a date and time window. Team members can order between start and end.</div>
      </div>

      <div className="box shadow" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 560 }}>
        <div className="row" style={{ gap: 12 }}>
          <div style={{ flex: 2 }}>
            <div className="eyebrow">date</div>
            <div className="field" style={{ justifyContent: 'space-between' }}>
              <span>Fri 14 May 2026</span>
              <span style={{ fontSize: 15 }} aria-hidden="true">📅</span>
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <div className="eyebrow">start time</div>
            <Field value="11:30" />
          </div>
          <div style={{ flex: 1 }}>
            <div className="eyebrow">end time</div>
            <Field value="12:00" />
          </div>
        </div>

        <div className="row" style={{ gap: 12, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <div className="eyebrow">grace period</div>
            <div className="row" style={{ alignItems: 'center', gap: 6 }}>
              <Field value="– 2 +" w={120} />
              <span className="faint" style={{ fontSize: 13 }}>min</span>
            </div>
          </div>
          <div style={{ flex: 2 }}>
            <span className="faint" style={{ fontSize: 12 }}>orders submitted up to <span className="mono">12:02</span> still accepted</span>
          </div>
        </div>

        <hr className="sketch" />

        <div>
          <div className="eyebrow">team ordering link · stays the same for every session</div>
          <div className="row" style={{ alignItems: 'center', gap: 8, marginTop: 4 }}>
            <span className="field mono" style={{ flex: 1, fontSize: 13 }}>orders.app/x7k9mP2qRvL5j</span>
            <Btn>⧉ copy</Btn>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <Btn>cancel</Btn>
        <Btn kind="accent">open session</Btn>
      </div>
    </div>
  </div>;


/* ============== success state — right after submit ============== */
const D1_TeamSuccess = () =>
<div className="wf" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 24 }}>
    <div className="h2">🍕 Engineering · pizza day</div>
    <Sq />

    <div style={{ display: 'flex', justifyContent: 'center' }}>
      <div className="box shadow" style={{ padding: 28, maxWidth: 520, width: '100%', display: 'flex', flexDirection: 'column', gap: 14, textAlign: 'center' }}>
        <div className="scribble" style={{ fontSize: 80, color: 'var(--accent)', lineHeight: 1 }}>✓</div>
        <H1>Order placed!</H1>
        <div className="soft">3 pizzas heading to the CPO.</div>
        <div className="soft" style={{ fontSize: 13 }}>
          Orders can't be edited after submission. Contact your CPO if you change your mind.
        </div>
        <div className="row" style={{ justifyContent: 'center', gap: 10, marginTop: 4 }}>
          <Btn>add another order</Btn>
        </div>
      </div>
    </div>
  </div>;


/* ================================================================ *
 * DIRECTION 2 — MOBILE FIRST CARD STACK
 * "Phone screens. Big touch targets. CPO can run a session on the go."
 * ================================================================ */

const D2_Phones = () =>
<div className="wf" style={{ display: 'flex', gap: 18, padding: 20, justifyContent: 'center', alignItems: 'center' }}>
    {/* Phone 1: team order */}
    <div className="phone">
      <div style={{ marginTop: 16 }}>
        <div className="eyebrow">engineering · pizza day</div>
        <H2>Order yours</H2>
      </div>
      <div className="chip accent" style={{ marginTop: 6 }}>● closes in 06:42</div>
      <div className="col" style={{ marginTop: 12, gap: 8 }}>
        <Field value="your name" tone="var(--ink-faint)" />
        <div className="box tone" style={{ padding: 8 }}>
          <div className="eyebrow">pick a pizza</div>
          <div className="col" style={{ gap: 6, marginTop: 4 }}>
            {[['Margherita', '12.50', true], ['Diavola', '14.50'], ['Marinara', '10.00']].map(([n, p, sel]) =>
          <div key={n} className="field" style={{ justifyContent: 'space-between', borderColor: sel ? 'var(--accent)' : 'var(--ink)', background: sel ? 'var(--accent-soft)' : '#fff' }}>
                <span>{sel ? '● ' : '○ '}{n}</span><span className="mono">{p}</span>
              </div>
          )}
            <div className="faint" style={{ fontSize: 12, textAlign: 'center' }}>+ 4 more</div>
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <Field value="qty: 2" />
          <Field value="pin ••••" />
        </div>
        <Btn kind="accent" style={{ justifyContent: 'center', padding: '10px 14px' }}>place order</Btn>
      </div>
    </div>

    {/* Phone 2: confirm / modify */}
    <div className="phone">
      <div style={{ marginTop: 16 }}>
        <Eyebrow>order placed ✓</Eyebrow>
        <H2>You're in, Alice.</H2>
      </div>
      <div className="box tone" style={{ marginTop: 12, padding: 10 }}>
        <div className="mono" style={{ fontSize: 12 }}>order #a14</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
          <span>2× Margherita</span><span className="mono">25.00</span>
        </div>
        <hr className="sketch" />
        <div className="eyebrow">your pin</div>
        <div className="num-big" style={{ fontSize: 40 }}>• • • •</div>
        <div className="faint" style={{ fontSize: 12 }}>keep this. it lets you edit.</div>
      </div>
      <div className="col" style={{ marginTop: 12, gap: 8 }}>
        <Btn>modify order</Btn>
        <Btn kind="ghost">cancel order</Btn>
      </div>
      <div style={{ marginTop: 18, textAlign: 'center' }} className="faint">session closes 12:00</div>
    </div>

    {/* Phone 3: CPO on phone */}
    <div className="phone" style={{ background: '#1a1a1a', color: '#fbfaf6' }}>
      <div style={{ marginTop: 16, color: '#fbfaf6' }}>
        <div className="eyebrow" style={{ color: '#ddd' }}>cpo · live</div>
        <div className="h2" style={{ color: '#fff' }}>22 pizzas</div>
        <div style={{ opacity: .7, fontSize: 13 }}>14 orders · CHF 274.50</div>
      </div>
      <div className="num-big" style={{ color: 'var(--accent)', marginTop: 10, fontSize: 64 }}>06:42</div>
      <div className="faint" style={{ color: '#888', fontSize: 12, marginTop: -6 }}>until session closes</div>

      <div style={{ marginTop: 14 }}>
        <Eyebrow><span style={{ color: '#aaa' }}>top pizzas</span></Eyebrow>
        <div className="col" style={{ gap: 4, marginTop: 4 }}>
          {[['Margherita', '8'], ['Diavola', '5'], ['Marinara', '4'], ['Capricciosa', '3'], ['Q. Stagioni', '2']].map(([n, q]) =>
        <div key={n} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px dashed #444', padding: '4px 0' }}>
              <span>{n}</span><span className="mono">×{q}</span>
            </div>
        )}
        </div>
      </div>
      <div className="row" style={{ marginTop: 12, gap: 6 }}>
        <span className="chip" style={{ background: '#fff' }}>share link</span>
        <span className="chip" style={{ background: '#fff' }}>print</span>
        <span className="chip accent">close</span>
      </div>
    </div>

    <Note x={20} y={20} w={140} dir="right">"normal"<br />team-member<br />flow ↘</Note>
    <Note x={620} y={20} w={140} dir="left">CPO running<br />session from<br />the kitchen ↙</Note>
  </div>;


/* ================================================================ *
 * DIRECTION 3 — PIZZERIA SKEUO / TICKET METAPHOR
 * "Looks like a real pizzeria order pad. Playful, fits the brand."
 * ================================================================ */

const D3_MenuBoard = () =>
<div className="wf" style={{ background: '#1a1a1a', color: '#fbfaf6', padding: 0, overflow: 'hidden' }}>
    <div style={{ padding: '22px 28px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', borderBottom: '2px dashed #555' }}>
      <div>
        <div className="scribble" style={{ fontSize: 48, color: 'var(--accent)', lineHeight: 1 }}>Tonight at CPO</div>
        <div style={{ opacity: .7 }}>engineering team · order before 12:00</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div className="num-big" style={{ color: '#fff' }}>06:42</div>
        <div className="eyebrow" style={{ color: '#888' }}>session ends</div>
      </div>
    </div>

    <div style={{ padding: '20px 28px', display: 'grid', gridTemplateColumns: '1.4fr .8fr', gap: 22 }}>
      {/* menu board */}
      <div>
        <div className="eyebrow" style={{ color: '#888' }}>— menu —</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10 }}>
          {[
        ['Margherita', 'tomato · mozzarella · basil', '12.50'],
        ['Diavola', 'salame piccante · chilli', '14.50'],
        ['Marinara', 'tomato · garlic · oregano', '10.00'],
        ['Capricciosa', 'ham · artichoke · mushroom', '15.50'],
        ['Q. Stagioni', 'four seasons', '15.00'],
        ['Bianca', 'no tomato · ricotta', '13.00']].
        map(([n, d, p]) =>
        <div key={n} style={{ padding: '8px 0', borderBottom: '1.5px dotted #555', display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <div>
                <div className="scribble" style={{ fontSize: 22, lineHeight: 1 }}>{n}</div>
                <div style={{ opacity: .6, fontSize: 12 }}>{d}</div>
              </div>
              <div className="scribble" style={{ fontSize: 22, color: 'var(--accent)' }}>{p}</div>
            </div>
        )}
        </div>
      </div>

      {/* order pad */}
      <div className="ticket" style={{ background: '#fbfaf6', color: 'var(--ink)', padding: '18px 16px' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="scribble" style={{ fontSize: 22 }}>— order pad —</div>
          <div className="mono" style={{ fontSize: 10 }}>#A-014</div>
        </div>
        <hr className="sketch" />
        <div className="eyebrow">name</div>
        <div className="field" style={{ marginBottom: 8 }}>Alice _________</div>
        <div className="eyebrow">pizza</div>
        <div className="field" style={{ marginBottom: 8 }}>▾ Margherita</div>
        <div className="row">
          <div style={{ flex: 1 }}>
            <div className="eyebrow">qty</div>
            <div className="field">– 2 +</div>
          </div>
          <div style={{ flex: 1 }}>
            <div className="eyebrow">pin</div>
            <div className="field">• • • •</div>
          </div>
        </div>
        <div style={{ marginTop: 10, textAlign: 'center' }}>
          <Btn kind="accent">stamp & submit</Btn>
        </div>
        <div className="mono faint" style={{ fontSize: 10, marginTop: 10, textAlign: 'center' }}>
          — — — tear here — — —
        </div>
      </div>
    </div>
  </div>;


const D3_Kitchen = () =>
<div className="wf" style={{ padding: 22, background: 'var(--paper-2)' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
      <H1>Kitchen ticket — to pizzeria</H1>
      <div className="row" style={{ gap: 6 }}>
        <Btn>⎙ print</Btn>
        <Btn>⤓ .txt</Btn>
      </div>
    </div>
    <div className="soft">Aggregated. Names & IPs hidden in this view.</div>

    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginTop: 14 }}>
      {[
    ['Margherita', '8', '100.00'],
    ['Diavola', '5', '72.50'],
    ['Marinara', '4', '40.00'],
    ['Capricciosa', '3', '46.50'],
    ['Q. Stagioni', '2', '30.00'],
    ['Bianca', '0', '—']].
    map(([n, q, t], i) =>
    <div key={n} className={`ticket ${i % 2 ? 'tilt-r' : 'tilt-l'}`} style={{ padding: '14px 14px', background: '#fff' }}>
          <div className="mono faint" style={{ fontSize: 10 }}>SLIP #{i + 1}</div>
          <div className="scribble" style={{ fontSize: 28 }}>{n}</div>
          <hr className="sketch" />
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="soft">qty</span>
            <span className="num-big" style={{ fontSize: 38, color: q === '0' ? 'var(--ink-faint)' : 'var(--ink)' }}>{q}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="soft">CHF total</span>
            <span className="mono">{t}</span>
          </div>
        </div>
    )}
    </div>

    <div className="row" style={{ marginTop: 18, justifyContent: 'space-between', alignItems: 'center' }}>
      <div className="scribble" style={{ fontSize: 26 }}>grand total: <span style={{ color: 'var(--accent)' }}>22 pies · CHF 289.00</span></div>
      <div className="chip">view 1: distribution · <b>view 2: pizzeria</b></div>
    </div>
  </div>;


/* ================================================================ *
 * DIRECTION 4 — LIVE COMMAND CONSOLE
 * "Big realtime control room view for the CPO during the session."
 * ================================================================ */

const D4_Console = () =>
<div className="wf dense" style={{ display: 'grid', gridTemplateColumns: '2fr 1.2fr', gridTemplateRows: 'auto 1fr auto', gap: 12, padding: 16 }}>
    {/* top bar */}
    <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 14 }}>
      <div>
        <Eyebrow>session · engineering team</Eyebrow>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
          <div className="scribble" style={{ fontSize: 30 }}>● LIVE</div>
          <div className="soft mono">orders.app/x7k9mP2qRvL5j</div>
          <Btn>copy</Btn>
          <Btn>qr</Btn>
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <Eyebrow>closes in</Eyebrow>
        <div className="num-big" style={{ color: 'var(--accent)' }}>06:42</div>
        <div className="faint mono" style={{ fontSize: 11 }}>+2:00 grace</div>
      </div>
    </div>

    {/* left: live ticker */}
    <div className="box thin" style={{ display: 'flex', flexDirection: 'column', padding: 12, minHeight: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <H2>Live feed</H2>
        <div className="row" style={{ gap: 6 }}>
          <span className="chip solid">all</span>
          <span className="chip">submissions</span>
          <span className="chip">cpo deletes</span>
          <span className="chip">rate-limit</span>
        </div>
      </div>
      <hr className="sketch" />
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {[
      { t: '11:36:42', kind: 'NEW', who: 'Alice', pizzas: ['Margherita', 'Diavola', 'Marinara'], total: '37.00', ip: '192.168.1.21' },
      { t: '11:36:18', kind: 'NEW', who: 'Bob', pizzas: ['Diavola'], total: '14.50', ip: '192.168.1.21' },
      { t: '11:35:55', kind: 'NEW', who: 'Chen', pizzas: ['Quattro Stagioni', 'Margherita'], total: '27.50', ip: '10.0.0.4' },
      { t: '11:35:14', kind: 'NEW', who: 'Dani', pizzas: ['Margherita', 'Margherita'], total: '25.00', ip: '192.168.1.34' },
      { t: '11:34:48', kind: 'DEL', who: '—', pizzas: ['CPO removed: qwerty / Diavola'], total: '—', ip: '10.0.0.4', faint: true },
      { t: '11:34:02', kind: 'NEW', who: 'Finn', pizzas: ['Marinara', 'Marinara', 'Marinara'], total: '30.00', ip: '192.168.1.7' },
      { t: '11:33:30', kind: '429', who: '—', pizzas: ['rate limit hit'], total: '—', ip: '10.0.0.4', faint: true },
      { t: '11:33:12', kind: 'NEW', who: 'Gus', pizzas: ['Capricciosa'], total: '15.50', ip: '192.168.1.8' }].
      map((r, i) => {
        const tone = r.kind === 'NEW' ? 'accent' : r.kind === 'DEL' ? 'solid' : '';
        return (
          <div key={i} className={`box thin ${r.faint ? 'tone' : ''}`} style={{ padding: '6px 10px', display: 'flex', gap: 10, alignItems: 'center', opacity: r.faint ? .6 : 1 }}>
              <span className="mono faint" style={{ fontSize: 11, width: 56 }}>{r.t}</span>
              <span className={`chip ${tone}`} style={{ width: 48, justifyContent: 'center' }}>{r.kind}</span>
              <span style={{ width: 56, fontWeight: 700 }}>{r.who}</span>
              <span className="grow" style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {r.pizzas.map((p, j) =>
              <span key={j} className="chip tone" style={{ fontSize: 11, padding: '1px 7px' }}>{p}</span>
              )}
              </span>
              <span className="mono" style={{ width: 50, textAlign: 'right' }}>{r.total !== '—' ? `CHF ${r.total}` : '—'}</span>
              <span className="tag-x" style={{ width: 80 }}>{r.ip}</span>
              <span className="tag-x">✕</span>
            </div>);

      })}
      </div>
      <div className="faint mono" style={{ fontSize: 10, marginTop: 6 }}>
        ▸ one submission can carry multiple pizzas — each becomes its own order row
      </div>
    </div>

    {/* right: aggregate */}
    <div className="col" style={{ minHeight: 0 }}>
      <div className="box thin" style={{ padding: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Eyebrow>pizzeria view · totals</Eyebrow>
          <span className="tag-x">type · count · CHF</span>
        </div>
        <div className="col" style={{ gap: 4, marginTop: 6 }}>
          {[
        ['Margherita', 8, 100],
        ['Diavola', 5, 72.5],
        ['Marinara', 4, 40],
        ['Capricciosa', 3, 46.5],
        ['Q. Stagioni', 2, 30]].
        map(([n, q, t]) =>
        <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 100 }}>{n}</span>
              <div style={{ flex: 1, height: 14, background: 'var(--paper-2)', borderRadius: 7, position: 'relative', border: '1.5px solid var(--ink)' }}>
                <div style={{ position: 'absolute', inset: 0, width: `${q * 10}%`, background: 'var(--accent)', borderRadius: 5 }} />
              </div>
              <span className="mono" style={{ width: 28, textAlign: 'right' }}>×{q}</span>
              <span className="mono soft" style={{ width: 48, textAlign: 'right' }}>CHF {t}</span>
            </div>
        )}
        </div>
      </div>

      <div className="box thin" style={{ padding: 12 }}>
        <Eyebrow>flags · cpo oversight (IP)</Eyebrow>
        <div className="col" style={{ gap: 6, marginTop: 6, fontSize: 13 }}>
          <div className="row" style={{ gap: 6 }}><span className="chip accent">!</span><span className="grow">5 pizzas from same IP <span className="mono faint">192.168.1.21</span> in 2'</span></div>
          <div className="row" style={{ gap: 6 }}><span className="chip">i</span><span className="grow">unfamiliar name “qwerty” — review</span></div>
          <div className="row" style={{ gap: 6 }}><span className="chip">i</span><span className="grow">rate-limit hit ×2 on <span className="mono">10.0.0.4</span> (HTTP 429)</span></div>
        </div>
      </div>

      <div className="box thin tone" style={{ padding: 12 }}>
        <Eyebrow>session controls</Eyebrow>
        <div className="row" style={{ gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
          <Btn>edit menu</Btn>
          <Btn>⎙ print summary</Btn>
          <Btn>⤓ export .tsv</Btn>
          <Btn kind="accent">close now</Btn>
        </div>
      </div>
    </div>

    {/* footer */}
    <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 10, alignItems: 'center' }}>
      <div className="chip tone">9 members</div>
      <div className="chip tone">22 pizzas</div>
      <div className="chip tone">CHF 289.00</div>
      <div style={{ flex: 1 }} />
      <div className="faint mono" style={{ fontSize: 11 }}>connected · SSE stream · 3 viewers</div>
    </div>
  </div>;


const D4_Setup = () =>
<div className="wf" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 12 }}>
    <H1>New session</H1>
    <div className="soft">Configure a one-off ordering window. The link becomes active at start time.</div>
    <div className="box shadow" style={{ padding: 16, maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div className="row">
        <div style={{ flex: 2 }}>
          <Eyebrow>date</Eyebrow>
          <Field value="Fri 14 May 2026" />
        </div>
        <div style={{ flex: 1 }}>
          <Eyebrow>start</Eyebrow>
          <Field value="11:30" />
        </div>
        <div style={{ flex: 1 }}>
          <Eyebrow>end</Eyebrow>
          <Field value="12:00" />
        </div>
      </div>
      <div className="box tone" style={{ padding: '8px 12px', display: 'flex', gap: 14, alignItems: 'center' }}>
        <Eyebrow>fixed by spec</Eyebrow>
        <span className="soft" style={{ fontSize: 13 }}>2-min grace · 1 submission per IP / 5s · 1 pizza per order row</span>
      </div>
      <hr className="sketch" />
      <Eyebrow>menu snapshot (live link to menu manager)</Eyebrow>
      <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
        {['Margherita 12.50', 'Diavola 14.50', 'Marinara 10.00', 'Q. Stagioni 15.00', 'Capricciosa 15.50', 'Bianca 13.00'].map((p) =>
      <span key={p} className="chip">{p}</span>
      )}
        <span className="chip tone">+ edit menu</span>
      </div>
      <div className="row" style={{ marginTop: 8 }}>
        <Btn kind="accent">create &amp; generate link</Btn>
        <Btn kind="ghost">cancel</Btn>
      </div>
    </div>

    <Note x={500} y={250}>← strict 2-min<br />grace, per spec</Note>
  </div>;


/* ================================================================ *
 * DIRECTION 5 — CONVERSATIONAL STEPPER
 * "One question at a time. Feels like a chat. Nothing to scroll on phone."
 * ================================================================ */

const D5_Step = ({ n, total = 4, q, body, actions, hint }) =>
<div className="wf" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}>
    <div className="row" style={{ alignItems: 'center' }}>
      <span className="scribble" style={{ fontSize: 22 }}>🍕 CPO</span>
      <div style={{ flex: 1 }} />
      <div className="row" style={{ gap: 4 }}>
        {[...Array(total)].map((_, i) =>
      <span key={i} style={{ width: 22, height: 4, background: i < n ? 'var(--ink)' : 'var(--paper-2)', border: '1px solid var(--ink)', borderRadius: 2 }} />
      )}
      </div>
      <span className="mono faint" style={{ marginLeft: 8, fontSize: 11 }}>{n}/{total}</span>
    </div>

    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 14 }}>
      <div className="scribble" style={{ fontSize: 38, lineHeight: 1.1, maxWidth: 520 }}>{q}</div>
      {body}
      {hint && <div className="soft" style={{ fontSize: 13 }}>{hint}</div>}
    </div>

    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
      <Btn kind="ghost">← back</Btn>
      <div className="row" style={{ gap: 8 }}>{actions}</div>
    </div>
  </div>;


const D5_Welcome = () =>
<D5_Step n={1} q={<>Hi! What should we call you on the order?</>}
body={
<div className="box shadow" style={{ padding: 14, maxWidth: 460 }}>
        <Field value="Alice ____________________________" />
      </div>
}
hint="The CPO sees this name in the summary."
actions={<><Btn kind="accent">next →</Btn></>} />;



const D5_Pick = () =>
<D5_Step n={2} q={<>Alice, what are you in the mood for?</>}
body={
<div className="col" style={{ maxWidth: 540, gap: 8 }}>
        {[
  ['Margherita', 'tomato · mozzarella · basil', '12.50', true],
  ['Diavola', 'salame piccante · chilli', '14.50'],
  ['Marinara', 'tomato · garlic · oregano', '10.00'],
  ['Quattro Stagioni', 'four seasons', '15.00'],
  ['Capricciosa', 'ham · artichoke · mushroom', '15.50']].
  map(([n, d, p, sel]) =>
  <div key={n} className="box" style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 12, background: sel ? 'var(--accent-soft)' : '#fff', borderColor: sel ? 'var(--accent)' : 'var(--ink)' }}>
            <span style={{ width: 16 }}>{sel ? '●' : '○'}</span>
            <div style={{ flex: 1 }}>
              <div className="scribble" style={{ fontSize: 22 }}>{n}</div>
              <div className="soft" style={{ fontSize: 12 }}>{d}</div>
            </div>
            <span className="mono">CHF {p}</span>
          </div>
  )}
      </div>
}
actions={<><Btn>skip</Btn><Btn kind="accent">next →</Btn></>} />;



const D5_Confirm = () =>
<D5_Step n={4} q={<>How many, and pick a PIN.</>}
body={
<div className="row" style={{ gap: 14, maxWidth: 560 }}>
        <div className="box shadow" style={{ padding: 14, flex: 1 }}>
          <Eyebrow>quantity (max 10)</Eyebrow>
          <div className="row" style={{ alignItems: 'center', gap: 10, marginTop: 6 }}>
            <span className="btn" style={{ padding: '4px 12px' }}>–</span>
            <span className="num-big">2</span>
            <span className="btn" style={{ padding: '4px 12px' }}>+</span>
          </div>
        </div>
        <div className="box shadow" style={{ padding: 14, flex: 1 }}>
          <Eyebrow>PIN (4–6 digits)</Eyebrow>
          <div className="row" style={{ gap: 6, marginTop: 6 }}>
            {[3, 7, 4, 1].map((d, i) =>
      <span key={i} className="field mono" style={{ width: 36, justifyContent: 'center', fontSize: 20 }}>{d}</span>
      )}
            <span className="field mono" style={{ width: 36, justifyContent: 'center', color: 'var(--ink-faint)' }}>_</span>
            <span className="field mono" style={{ width: 36, justifyContent: 'center', color: 'var(--ink-faint)' }}>_</span>
          </div>
          <div className="soft" style={{ fontSize: 12, marginTop: 6 }}>Use this to change or cancel later.</div>
        </div>
      </div>
}
actions={<><Btn kind="accent">stamp my order ✓</Btn></>} />;



/* ============== closed / error state ============== */
const D_Closed = () =>
<div className="wf" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: 40, gap: 14, position: 'relative' }}>
    <span className="btn" style={{ position: 'absolute', top: 16, right: 16, padding: '4px 10px', fontSize: 18, lineHeight: 1, transform: 'rotate(0deg)' }} aria-label="close">✕</span>
    <div className="scribble" style={{ fontSize: 64, color: 'var(--accent)' }}>Session is closed.</div>
    <div className="soft">No more orders for today.</div>
  </div>;


window.Screens = {
  D1_CPOHome, D1_CPOHomePizzeria, D1_TeamOrder, D1_TeamSuccess, D1_Menu, D1_NewSession,
  D2_Phones,
  D3_MenuBoard, D3_Kitchen,
  D4_Console, D4_Setup,
  D5_Welcome, D5_Pick, D5_Confirm,
  D_Closed
};