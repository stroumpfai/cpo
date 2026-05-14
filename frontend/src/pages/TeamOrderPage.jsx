import { useParams } from 'react-router-dom';

export function TeamOrderPage() {
  const { link } = useParams();
  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-surface)', display: 'flex', flexDirection: 'column' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 24px',
        background: 'var(--color-bg)',
        borderBottom: '1px solid var(--color-border)',
      }}>
        <span style={{ fontWeight: 700 }}>🍕 pizza day</span>
      </header>
      <div style={{ padding: 32 }}>
        <div className="card card-pad text-soft text-sm">
          Team order page for link <code className="mono">{link}</code> — coming in Phase 11.
        </div>
      </div>
    </div>
  );
}
