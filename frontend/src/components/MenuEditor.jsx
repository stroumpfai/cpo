import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

/**
 * Editor for one menu: website URL, item list (add/edit/delete), export/import.
 * Re-fetches its items whenever `menu.id` changes; calls `onChanged` after any
 * mutation that the parent menu list should reflect (item counts, url).
 */
export function MenuEditor({ menu, currency, onChanged }) {
  const [pizzas, setPizzas]       = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName]   = useState('');
  const [editPrice, setEditPrice] = useState('');
  const [editError, setEditError] = useState('');
  const [newName, setNewName]     = useState('');
  const [newPrice, setNewPrice]   = useState('');
  const [addError, setAddError]   = useState('');
  const addNameRef = useRef(null);
  const importFileRef = useRef(null);

  const [url, setUrl]             = useState(menu.pizzeria_url ?? '');
  const [urlSaved, setUrlSaved]   = useState(menu.pizzeria_url ?? '');
  const [urlSaving, setUrlSaving] = useState(false);
  const [urlError, setUrlError]   = useState('');
  const [importError, setImportError] = useState('');

  async function loadPizzas() {
    try {
      setPizzas(await api.get(`/cpo/menus/${menu.id}/pizzas`));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    setError('');
    setEditingId(null);
    setUrl(menu.pizzeria_url ?? '');
    setUrlSaved(menu.pizzeria_url ?? '');
    setUrlError('');
    setImportError('');
    loadPizzas();
  }, [menu.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  async function exportMenu() {
    try {
      // Auth rides on the httpOnly session cookie
      const res = await fetch(`/api/cpo/menus/${menu.id}/export`);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = 'menu.json';
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleImportFile(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setImportError('');
    let parsed;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setImportError('Invalid JSON file.');
      return;
    }
    try {
      await api.post(`/cpo/menus/${menu.id}/import`, parsed);
      loadPizzas();
      onChanged?.();
    } catch (err) {
      setImportError(err.message);
    }
  }

  async function saveUrl() {
    const trimmed = url.trim();
    if (trimmed && !/^https?:\/\/.+/.test(trimmed)) {
      setUrlError('URL must start with http:// or https://');
      return;
    }
    setUrlError('');
    setUrlSaving(true);
    try {
      await api.patch(`/cpo/menus/${menu.id}`, { pizzeria_url: trimmed || null });
      setUrlSaved(trimmed);
      onChanged?.();
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
      await api.put(`/cpo/menus/${menu.id}/pizzas/${pizzaId}`, { name: editName.trim(), price });
      setEditingId(null);
      loadPizzas();
    } catch (err) {
      setEditError(err.message);
    }
  }

  async function deletePizza(pizzaId) {
    if (!globalThis.confirm('Delete this item from the menu?')) return;
    try {
      await api.delete(`/cpo/menus/${menu.id}/pizzas/${pizzaId}`);
      loadPizzas();
      onChanged?.();
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
      await api.post(`/cpo/menus/${menu.id}/pizzas`, { name: newName.trim(), price });
      setNewName('');
      setNewPrice('');
      loadPizzas();
      onChanged?.();
      addNameRef.current?.focus();
    } catch (err) {
      setAddError(err.message);
    }
  }

  const ROW_STYLE = { padding: '4px 8px', fontSize: 'var(--font-size-xs)' };

  return (
    <div>
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Export / Import toolbar */}
      <div className="row" style={{ gap: 8, marginBottom: 16 }}>
        <button className="btn btn-ghost" onClick={exportMenu}>↓ export JSON</button>
        <button className="btn btn-ghost" onClick={() => importFileRef.current?.click()}>↑ import JSON</button>
        <input
          ref={importFileRef}
          type="file"
          accept=".json,application/json"
          style={{ display: 'none' }}
          onChange={handleImportFile}
        />
      </div>
      {importError && <div className="alert alert-error" style={{ marginBottom: 16 }}>{importError}</div>}

      {/* Restaurant URL */}
      <div className="card card-pad" style={{ maxWidth: 640, marginBottom: 16 }}>
        <div className="form-group" style={{ marginBottom: urlError ? 4 : 0 }}>
          <label className="form-label" htmlFor="restaurant-url">Restaurant website</label>
          <div className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
            <input
              id="restaurant-url"
              className="form-input"
              type="url"
              placeholder="https://restaurant.example.com"
              value={url}
              onChange={e => { setUrl(e.target.value); setUrlError(''); }}
              onKeyDown={e => e.key === 'Enter' && saveUrl()}
              style={{ flex: 1 }}
            />
            <button
              className="btn btn-primary"
              onClick={saveUrl}
              disabled={urlSaving || url.trim() === urlSaved}
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
                <th>Item name</th>
                <th style={{ textAlign: 'right', width: 130 }}>{`Price (${currency})`}</th>
                <th style={{ width: 160 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pizzas.length === 0 && (
                <tr>
                  <td colSpan={3} className="text-soft text-sm" style={{ textAlign: 'center', padding: 20 }}>
                    No items yet — add one below.
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
                    placeholder="type item name…"
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
