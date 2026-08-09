import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api.js';
import { translateApiError } from '../i18n/apiError.js';
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

  const { t } = useTranslation();

  async function loadMenus({ keepSelection = true } = {}) {
    try {
      const list = await api.get('/cpo/menus');
      setMenus(list);
      setSelectedId(prev => {
        if (keepSelection && prev && list.some(m => m.id === prev)) return prev;
        return (list.find(m => m.is_default) ?? list[0])?.id ?? null;
      });
    } catch (err) {
      setError(translateApiError(err, t));
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
      setError(translateApiError(err, t));
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
      setError(translateApiError(err, t));
    }
  }

  async function setDefault(menuId) {
    setError('');
    try {
      await api.post(`/cpo/menus/${menuId}/default`);
      loadMenus();
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  async function deleteMenu(menu) {
    if (!globalThis.confirm(t('menus.deleteConfirm', { name: menu.name }))) return;
    setError('');
    try {
      await api.delete(`/cpo/menus/${menu.id}`);
      loadMenus({ keepSelection: false });
    } catch (err) {
      setError(translateApiError(err, t));
    }
  }

  const selectedMenu = menus.find(m => m.id === selectedId) ?? null;
  const ROW_BTN = { padding: '4px 8px', fontSize: 'var(--font-size-xs)' };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{t('menus.title')}</h1>
          <p className="page-subtitle">
            {t('menus.subtitle')}
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Menu list */}
      <div className="card" style={{ maxWidth: 640, marginBottom: 20 }}>
        {loading ? (
          <div className="card-pad text-soft text-sm">{t('common.loading')}</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('menus.colMenu')}</th>
                <th style={{ width: 90, textAlign: 'right' }}>{t('menus.colItems')}</th>
                <th style={{ width: 260 }}>{t('menus.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {menus.length === 0 && (
                <tr>
                  <td colSpan={3} className="text-soft text-sm" style={{ textAlign: 'center', padding: 20 }}>
                    {t('menus.empty')}
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
                          onClick={() => saveRename(menu.id)}>{t('menus.save')}</button>
                        <button className="btn btn-ghost" style={ROW_BTN}
                          onClick={() => setRenamingId(null)}>{t('menus.cancel')}</button>
                      </div>
                    </td>
                  ) : (
                    <td>
                      <span style={{ fontWeight: menu.id === selectedId ? 600 : 400 }}>
                        {menu.name}
                      </span>
                      {menu.is_default && (
                        <span className="text-soft text-xs" style={{ marginLeft: 8 }}>{t('menus.isDefault')}</span>
                      )}
                    </td>
                  )}
                  <td className="td-mono" style={{ textAlign: 'right' }}>{menu.pizza_count}</td>
                  <td onClick={e => e.stopPropagation()}>
                    <div className="row" style={{ gap: 6 }}>
                      <button className="btn btn-ghost" style={ROW_BTN}
                        onClick={() => startRename(menu)}>{t('menus.rename')}</button>
                      {!menu.is_default && (
                        <button className="btn btn-ghost" style={ROW_BTN}
                          onClick={() => setDefault(menu.id)}>{t('menus.makeDefault')}</button>
                      )}
                      <button
                        className="btn btn-ghost"
                        style={{ ...ROW_BTN, color: 'var(--color-accent)' }}
                        onClick={() => deleteMenu(menu)}
                      >{t('menus.delete')}</button>
                    </div>
                  </td>
                </tr>
              ))}

              {/* Add-new row */}
              <tr style={{ background: 'var(--color-surface)' }}>
                <td colSpan={2}>
                  <input
                    className="form-input"
                    placeholder={t('menus.newMenuPlaceholder')}
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
                  >{t('menus.newMenu')}</button>
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
            {t('menus.editing')} <strong>{selectedMenu.name}</strong>
          </h2>
          <MenuEditor menu={selectedMenu} currency={currency} onChanged={loadMenus} />
        </>
      )}
    </div>
  );
}
