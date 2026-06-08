'use client';
import { useEffect, useMemo, useState } from 'react';
import { createMasterValue, deleteMasterValue, fetchMasterValues, updateMasterValue } from '../lib/api';
import { useConfirmAction } from './ConfirmActionProvider';

export default function SetupGroupsManager({ groups = [] }) {
  const confirmAction = useConfirmAction();
  const [rows, setRows] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({ value: '', code: '', group_name: '' });

  async function load() {
    setRows(await fetchMasterValues());
  }
  useEffect(() => { load().catch(console.error); }, []);

  const byGroup = useMemo(() => {
    const map = {};
    for (const g of groups) map[g.group_name] = [];
    for (const row of rows) {
      if (map[row.group_name]) map[row.group_name].push(row);
    }
    return map;
  }, [rows, groups]);

  async function save(groupName) {
    const draft = drafts[groupName] || { value: '', code: '' };
    if (!draft.value?.trim()) return;
    await createMasterValue({ group_name: groupName, value: draft.value, code: draft.code || null });
    setDrafts(d => ({ ...d, [groupName]: { value: '', code: '' } }));
    await load();
  }

  async function saveEdit() {
    await updateMasterValue(editingId, editDraft);
    setEditingId(null);
    setEditDraft({ value: '', code: '', group_name: '' });
    await load();
  }

  return (
    <div className="stack">
      {groups.map(group => {
        const draft = drafts[group.group_name] || { value: '', code: '' };
        const items = byGroup[group.group_name] || [];
        return (
          <section className="section" key={group.group_name}>
            <div className="row" style={{ justifyContent:'space-between' }}>
              <div>
                <h3>{group.label}</h3>
                {group.help && <div className="muted small">{group.help}</div>}
              </div>
              <span className="badge">{items.length}</span>
            </div>
            <div className="form-grid">
              <label>Value
                <input value={draft.value} placeholder={group.placeholder || group.label}
                  onChange={e => setDrafts(d => ({ ...d, [group.group_name]: { ...draft, value: e.target.value } }))} />
              </label>
              <label>Code
                <input value={draft.code} placeholder={group.codePlaceholder || 'Optional code'}
                  onChange={e => setDrafts(d => ({ ...d, [group.group_name]: { ...draft, code: e.target.value } }))} />
              </label>
              <div className="align-end">
                <button type="button" onClick={() => save(group.group_name)}>Add</button>
              </div>
            </div>
            <table className="table">
              <thead><tr><th>Value</th><th>Code</th><th></th></tr></thead>
              <tbody>
                {items.map(row => (
                  <tr key={row.id}>
                    <td>{editingId === row.id ? <input value={editDraft.value} onChange={e => setEditDraft(d => ({ ...d, value: e.target.value }))} /> : row.value}</td>
                    <td>{editingId === row.id ? <input value={editDraft.code || ''} onChange={e => setEditDraft(d => ({ ...d, code: e.target.value }))} /> : (row.code || '')}</td>
                    <td className="row">
                      {editingId === row.id ? (
                        <>
                          <button className="secondary" type="button" onClick={saveEdit}>Save</button>
                          <button className="secondary" type="button" onClick={() => { setEditingId(null); setEditDraft({ value: '', code: '', group_name: '' }); }}>Cancel</button>
                        </>
                      ) : (
                        <>
                          <button className="secondary" type="button" onClick={() => { setEditingId(row.id); setEditDraft({ value: row.value || '', code: row.code || '', group_name: row.group_name || '' }); }}>Edit</button>
                          <button className="secondary" type="button" onClick={async () => { if (await confirmAction({ title: `Delete ${row.value}?`, description: 'Remove only setup values that are no longer used by operational records.' })) { await deleteMasterValue(row.id); await load(); } }}>Delete</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
                {!items.length && <tr><td colSpan="3" className="muted">No values yet.</td></tr>}
              </tbody>
            </table>
          </section>
        );
      })}
    </div>
  );
}
