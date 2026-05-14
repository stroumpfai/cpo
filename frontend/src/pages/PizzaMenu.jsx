import { useNavigate } from 'react-router-dom';

export function PizzaMenu() {
  const navigate = useNavigate();
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">List of Pizzas</h1>
          <p className="page-subtitle">Your menu persists across sessions.</p>
        </div>
        <button className="btn btn-ghost" onClick={() => navigate('/dashboard')}>✕ close</button>
      </div>
      <div className="card card-pad text-soft text-sm">
        Pizza menu editor (inline add / edit / delete) — Phase 10.
      </div>
    </div>
  );
}
