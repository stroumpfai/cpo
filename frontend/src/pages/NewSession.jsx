import { useNavigate } from 'react-router-dom';

export function NewSession() {
  const navigate = useNavigate();
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Open a new session</h1>
          <p className="page-subtitle">Date, time window, and grace period — coming in Phase 10</p>
        </div>
        <button className="btn btn-ghost" onClick={() => navigate('/dashboard')}>✕ close</button>
      </div>
      <div className="card card-pad text-soft text-sm">
        Session creation form — Phase 10.
      </div>
    </div>
  );
}
