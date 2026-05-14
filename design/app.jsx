/* global React, ReactDOM, DesignCanvas, DCSection, DCArtboard, Screens */
const {
  D1_CPOHome, D1_CPOHomePizzeria, D1_TeamOrder, D1_TeamSuccess, D1_Menu, D1_NewSession,
  D_Closed,
} = Screens;

const Cover = () => (
  <div style={{
    width: '100%', height: '100%',
    display: 'flex', flexDirection: 'column',
    justifyContent: 'center', padding: '40px 48px',
    background: 'var(--paper)', boxSizing: 'border-box',
    fontFamily: 'Kalam, cursive',
  }}>
    <div className="eyebrow">wireframes · direction 1 · low-fi</div>
    <div className="scribble" style={{fontSize: 84, color: 'var(--ink)', lineHeight: .95, marginTop: 6}}>
      CPO
    </div>
    <div className="scribble" style={{fontSize: 36, color: 'var(--accent)', marginTop: -6}}>
      classic admin — selected direction
    </div>
    <div style={{height: 14}}/>
    <div className="soft" style={{maxWidth: 520, fontSize: 15}}>
      Familiar SaaS shape: sidebar nav, stat cards, tabbed tables. Lowest-risk, fastest to build,
      easiest to extend. Below: CPO dashboards (both summary tabs), open-a-session, list of pizzas,
      team order page, and the shared success / closed states.
    </div>
    <div style={{height: 20}}/>
    <div className="hand" style={{fontSize: 14, lineHeight: 1.6}}>
      <b>What's covered now:</b>
      <ul style={{margin: '6px 0 14px 0', paddingLeft: 18}}>
        <li>CPO dashboard — orders per person (live, countdown, IP, paid toggle)</li>
        <li>CPO dashboard — list for ordering at Pizzeria (aggregated)</li>
        <li>Open a new session — date/time + grace</li>
        <li>List of pizzas — menu manager</li>
        <li>Team order page — add-to-cart pattern</li>
        <li>Order placed — success state</li>
        <li>Session closed — shared idle state</li>
      </ul>
      <b>Next up — say the word and I'll add:</b>
      <ul style={{margin: '6px 0 0 0', paddingLeft: 18}}>
        <li>Admin panel (manage CPO accounts)</li>
        <li>CPO login + sessions index/history</li>
        <li>Mobile breakpoint for the team order page</li>
      </ul>
    </div>
    <div style={{flex: 1}}/>
    <div className="mono faint" style={{fontSize: 11}}>
      pan / pinch · drag artboards to reorder · double-click to rename · click ⤢ to focus
    </div>
  </div>
);

function App() {
  return (
    <DesignCanvas>
      <DCSection id="intro" title="Direction 1 — Classic admin" subtitle="Selected direction. Below: the current screens, ready to extend.">
        <DCArtboard id="cover" label="Cover" width={720} height={600}><Cover/></DCArtboard>
      </DCSection>

      <DCSection
        id="cpo"
        title="CPO surfaces"
        subtitle="What the Chief Pizza Officer sees once logged in."
      >
        <DCArtboard id="d1-home" label="Dashboard — orders per person" width={920} height={620}>
          <D1_CPOHome/>
        </DCArtboard>
        <DCArtboard id="d1-home-pz" label="Dashboard — list for pizzeria" width={920} height={620}>
          <D1_CPOHomePizzeria/>
        </DCArtboard>
        <DCArtboard id="d1-new" label="Open a new session" width={820} height={560}>
          <D1_NewSession/>
        </DCArtboard>
        <DCArtboard id="d1-menu" label="List of Pizzas" width={820} height={520}>
          <D1_Menu/>
        </DCArtboard>
      </DCSection>

      <DCSection
        id="team"
        title="Team-member surfaces"
        subtitle="What people ordering pizza see via the shared link."
      >
        <DCArtboard id="d1-order" label="Order page — add to cart" width={760} height={640}>
          <D1_TeamOrder/>
        </DCArtboard>
        <DCArtboard id="d1-success" label="Order placed — success state" width={560} height={440}>
          <D1_TeamSuccess/>
        </DCArtboard>
        <DCArtboard id="closed" label="Session closed" width={560} height={320}>
          <D_Closed/>
        </DCArtboard>
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
