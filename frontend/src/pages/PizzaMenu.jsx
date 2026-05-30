import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';

export function PizzaMenu() {
  const [pizzas, setPizzas]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editPrice, setEditPrice] = useState('');
  const [editError, setEditError] = useState('');
  const [newName, setNewName]   = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [addError, setAddError] = useState('');
  const addNameRef = useRef(null);
  const navigate = useNavigate();

  const [pizzeriaUrl, setPizzeriaUrl]       = useState('');
  const [urlSaved, setUrlSaved]             = useState('');
  const [urlSaving, setUrlSaving]           = useState(false);
  const [urlError, setUrlError]             = useState('');
  const [currency, setCurrency]             = useState('CHF');

  async function loadMenu() {
    try {
      const [pizzaList, urlData, cpo] = await Promise.all([
        api.get('/cpo/menu'),
        api.get('/cpo/menu/url'),
        api.get('/cpo/me'),
      ]);
      setPizzas(pizzaList);
      setPizzeriaUrl(urlData.pizzeria_url ?? '');
      setUrlSaved(urlData.pizzeria_url ?? '');
      setCurrency(cpo.currency ?? 'CHF');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadMenu(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function savePizzeriaUrl() {
    const trimmed = pizzeriaUrl.trim();
    if (trimmed && !/^https?:\/\/.+/.test(trimmed)) {
      setUrlError('URL must start with http:// or https://');
      return;
    }
    setUrlError('');
    setUrlSaving(true);
    try {
      await api.put('/cpo/menu/url', { pizzeria_url: trimmed || null });
      setUrlSaved(trimmed);
    } catch (err) {
      setUrlError(err.message);
    } finally {
      setUrlSaving(false);
    }
  }

  function startEdit(pizza) {
    setEditingId(pizza.id);
    setEditName(pizza.name);
    setEditPrice(String(pizza.price));
    setEditError('');
  }

  function cancelEdit() {
    setEditingId(null);
    setEditError('');
  }

  async function saveEdit(pizzaId) {
    const price = Number.parseFloat(editPrice);
    if (!editName.trim() || Number.isNaN(price) || price < 0.01) {
      setEditError('Name required and price must be ≥ 0.01');
      return;
    }
    setEditError('');
    try {
      await api.put(`/cpo/menu/${pizzaId}`, { name: editName.trim(), price });
      setEditingId(null);
      loadMenu();
    } catch (err) {
      setEditError(err.message);
    }
  }

  async function deletePizza(pizzaId) {
    if (!globalThis.confirm('Delete this pizza from the menu?')) return;
    try {
      await api.delete(`/cpo/menu/${pizzaId}`);
      loadMenu();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addPizza(e) {
    e.preventDefault();
    const price = Number.parseFloat(newPrice);
    if (!newName.trim() || Number.isNaN(price) || price < 0.01) {
      setAddError('Name required and price must be ≥ 0.01');
      return;
    }
    setAddError('');
    try {
      await api.post('/cpo/menu', { name: newName.trim(), price });
      setNewName('');
      setNewPrice('');
      loadMenu();
      addNameRef.current?.focus();
    } catch (err) {
      setAddError(err.message);
    }
  }

  const ROW_STYLE = { padding: '4px 8px', fontSize: 'var(--font-size-xs)' };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">List of Pizzas</h1>
          <p className="page-subtitle">Your menu persists across sessions.</p>
        </div>
        <button className="btn btn-ghost" onClick={() => navigate('/dashboard')}>✕ close</button>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Pizzeria URL */}
      <div className="card card-pad" style={{ maxWidth: 640, marginBottom: 16 }}>
        <div className="form-group" style={{ marginBottom: urlError ? 4 : 0 }}>
          <label className="form-label" htmlFor="pizzeria-url">Pizzeria website</label>
          <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
            <input
              id="pizzeria-url"
              className="form-input"
              type="url"
              placeholder="https://pizzeria.example.com"
              value={pizzeriaUrl}
              onChange={e => { setPizzeriaUrl(e.target.value); setUrlError(''); }}
              onKeyDown={e => e.key === 'Enter' && savePizzeriaUrl()}
              style={{ flex: 1 }}
            />
            <button
              className="btn btn-primary"
              onClick={savePizzeriaUrl}
              disabled={urlSaving || pizzeriaUrl.trim() === urlSaved}
            >
              {urlSaving ? 'Saving…' : 'save'}
            </button>
          </div>
          {urlError && <div className="alert alert-error text-xs mt-4">{urlError}</div>}
          {urlSaved && (
            <a
              href={urlSaved}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-soft"
              style={{ display: 'inline-block', marginTop: 6 }}
            >
              🔗 {urlSaved}
            </a>
          )}
        </div>
      </div>

      <div className="card" style={{ maxWidth: 640 }}>
        {loading ? (
          <div className="card-pad text-soft text-sm">Loading…</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Pizza name</th>
                <th style={{ textAlign: 'right', width: 130 }}>{`Price (${currency})`}</th>
                <th style={{ width: 160 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pizzas.length === 0 && (
                <tr>
                  <td colSpan={3} className="text-soft text-sm" style={{ textAlign: 'center', padding: 20 }}>
                    No pizzas yet — add one below.
                  </td>
                </tr>
              )}

              {pizzas.map(pizza => (
                <tr key={pizza.id}>
                  {editingId === pizza.id ? (
                    <>
                      <td>
                        <input
                          className="form-input"
                          value={editName}
                          onChange={e => setEditName(e.target.value)}
                          autoFocus
                        />
                        {editError && (
                          <div className="alert alert-error text-xs mt-4">{editError}</div>
                        )}
                      </td>
                      <td>
                        <input
                          className="form-input form-input-mono"
                          type="number" min="0.01" step="0.01"
                          value={editPrice}
                          onChange={e => setEditPrice(e.target.value)}
                          style={{ textAlign: 'right' }}
                        />
                      </td>
                      <td>
                        <div className="row" style={{ gap: 6 }}>
                          <button className="btn btn-primary" style={ROW_STYLE}
                            onClick={() => saveEdit(pizza.id)}>save</button>
                          <button className="btn btn-ghost" style={ROW_STYLE}
                            onClick={cancelEdit}>cancel</button>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td>{pizza.name}</td>
                      <td className="td-mono" style={{ textAlign: 'right' }}>
                        {pizza.price.toFixed(2)}
                      </td>
                      <td>
                        <div className="row" style={{ gap: 6 }}>
                          <button
                            className="btn btn-ghost" style={ROW_STYLE}
                            onClick={() => startEdit(pizza)}
                          >✎ edit</button>
                          <button
                            className="btn btn-ghost"
                            style={{ ...ROW_STYLE, color: 'var(--color-accent)' }}
                            onClick={() => deletePizza(pizza.id)}
                          >✕ delete</button>
                        </div>
                      </td>
                    </>
                  )}
                </tr>
              ))}

              {/* Add-new row */}
              <tr style={{ background: 'var(--color-surface)' }}>
                <td>
                  <input
                    ref={addNameRef}
                    className="form-input"
                    placeholder="type pizza name…"
                    value={newName}
                    onChange={e => { setNewName(e.target.value); setAddError(''); }}
                    onKeyDown={e => e.key === 'Enter' && addPizza(e)}
                  />
                  {addError && <div className="alert alert-error text-xs mt-4">{addError}</div>}
                </td>
                <td>
                  <input
                    className="form-input form-input-mono"
                    type="number" min="0.01" step="0.01"
                    placeholder="0.00"
                    value={newPrice}
                    onChange={e => { setNewPrice(e.target.value); setAddError(''); }}
                    onKeyDown={e => e.key === 'Enter' && addPizza(e)}
                    style={{ textAlign: 'right' }}
                  />
                </td>
                <td>
                  <button
                    className="btn btn-primary" style={ROW_STYLE}
                    onClick={addPizza}
                    disabled={!newName.trim() || !newPrice}
                  >add</button>
                </td>
              </tr>
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
