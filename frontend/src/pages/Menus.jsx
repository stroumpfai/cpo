import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { MenuEditor } from '../components/MenuEditor.jsx';

export function Menus() {
  const [menus, setMenus]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [currency, setCurrency] = useState('CHF');

  const [selectedId, setSelectedId] = useState(null);
  const [newMenuName, setNewMenuName] = useState('');
  const [creating, setCreating]     = useState(false);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  async function loadMenus({ keepSelection = true } = {}) {
    try {
      const list = await api.get('/cpo/menus');
      setMenus(list);
      setSelectedId(prev => {
        if (keepSelection && prev && list.some(m => m.id === prev)) return prev;
        return (list.find(m => m.is_default) ?? list[0])?.id ?? null;
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    api.get('/cpo/me').then(cpo => setCurrency(cpo.currency ?? 'CHF')).catch(() => {});
    loadMenus();
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  async function createMenu(e) {
    e.preventDefault();
    const name = newMenuName.trim();
    if (!name) return;
    setError('');
    setCreating(true);
    try {
      const created = await api.post('/cpo/menus', { name });
      setNewMenuName('');
      await loadMenus();
      setSelectedId(created.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  function startRename(menu) {
    setRenamingId(menu.id);
    setRenameValue(menu.name);
    setError('');
  }

  async function saveRename(menuId) {
    const name = renameValue.trim();
    if (!name) return;
    try {
      await api.patch(`/cpo/menus/${menuId}`, { name });
      setRenamingId(null);
      loadMenus();
    } catch (err) {
      setError(err.message);
    }
  }

  async function setDefault(menuId) {
    setError('');
    try {
      await api.post(`/cpo/menus/${menuId}/default`);
      loadMenus();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteMenu(menu) {
    if (!globalThis.confirm(`Delete the menu “${menu.name}” and all its items?`)) return;
    setError('');
    try {
      await api.delete(`/cpo/menus/${menu.id}`);
      loadMenus({ keepSelection: false });
    } catch (err) {
      setError(err.message);
    }
  }

  const selectedMenu = menus.find(m => m.id === selectedId) ?? null;
  const ROW_BTN = { padding: '4px 8px', fontSize: 'var(--font-size-xs)' };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Menus</h1>
          <p className="page-subtitle">
            Define one menu per restaurant. Your menus persist across sessions.
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Menu list */}
      <div className="card" style={{ maxWidth: 640, marginBottom: 20 }}>
        {loading ? (
          <div className="card-pad text-soft text-sm">Loading…</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Menu</th>
                <th style={{ width: 90, textAlign: 'right' }}>Items</th>
                <th style={{ width: 260 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {menus.length === 0 && (
                <tr>
                  <td colSpan={3} className="text-soft text-sm" style={{ textAlign: 'center', padding: 20 }}>
                    No menus yet — create your first one below.
                  </td>
                </tr>
              )}

              {menus.map(menu => (
                <tr
                  key={menu.id}
                  onClick={() => setSelectedId(menu.id)}
                  style={{
                    cursor: 'pointer',
                    background: menu.id === selectedId ? 'var(--color-surface)' : undefined,
                  }}
                >
                  {renamingId === menu.id ? (
                    <td onClick={e => e.stopPropagation()}>
                      <div className="row" style={{ gap: 6 }}>
                        <input
                          className="form-input"
                          value={renameValue}
                          onChange={e => setRenameValue(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && saveRename(menu.id)}
                          autoFocus
                        />
                        <button className="btn btn-primary" style={ROW_BTN}
                          onClick={() => saveRename(menu.id)}>save</button>
                        <button className="btn btn-ghost" style={ROW_BTN}
                          onClick={() => setRenamingId(null)}>cancel</button>
                      </div>
                    </td>
                  ) : (
                    <td>
                      <span style={{ fontWeight: menu.id === selectedId ? 600 : 400 }}>
                        {menu.name}
                      </span>
                      {menu.is_default && (
                        <span className="text-soft text-xs" style={{ marginLeft: 8 }}>★ default</span>
                      )}
                    </td>
                  )}
                  <td className="td-mono" style={{ textAlign: 'right' }}>{menu.pizza_count}</td>
                  <td onClick={e => e.stopPropagation()}>
                    <div className="row" style={{ gap: 6 }}>
                      <button className="btn btn-ghost" style={ROW_BTN}
                        onClick={() => startRename(menu)}>✎ rename</button>
                      {!menu.is_default && (
                        <button className="btn btn-ghost" style={ROW_BTN}
                          onClick={() => setDefault(menu.id)}>★ make default</button>
                      )}
                      <button
                        className="btn btn-ghost"
                        style={{ ...ROW_BTN, color: 'var(--color-accent)' }}
                        onClick={() => deleteMenu(menu)}
                      >✕ delete</button>
                    </div>
                  </td>
                </tr>
              ))}

              {/* Add-new row */}
              <tr style={{ background: 'var(--color-surface)' }}>
                <td colSpan={2}>
                  <input
                    className="form-input"
                    placeholder="new menu name…"
                    value={newMenuName}
                    onChange={e => setNewMenuName(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && createMenu(e)}
                  />
                </td>
                <td>
                  <button
                    className="btn btn-primary" style={ROW_BTN}
                    onClick={createMenu}
                    disabled={creating || !newMenuName.trim()}
                  >+ new menu</button>
                </td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      {/* Selected menu editor */}
      {selectedMenu && (
        <>
          <h2 className="text-sm text-soft" style={{ margin: '0 0 10px' }}>
            Editing: <strong>{selectedMenu.name}</strong>
          </h2>
          <MenuEditor menu={selectedMenu} currency={currency} onChanged={loadMenus} />
        </>
      )}
    </div>
  );
}
