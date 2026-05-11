'use client';
import { useEffect, useMemo, useState } from 'react';
import { createMasterValue, deleteMasterValue, fetchMasterValues, updateMasterValue } from '../../lib/api';

const presets = [
  'room_types', 'room_names', 'rate_plans', 'booking_channels',
  'inventory_categories', 'inventory_subcategories', 'units_of_measure',
  'departments', 'job_titles', 'employment_types', 'payment_methods', 'asset_classes'
];

export default function MasterDataPage() {
  const [groupName, setGroupName] = useState('room_types');
  const [value, setValue] = useState('');
  const [code, setCode] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [edit, setEdit] = useState({ value:'', code:'', group_name:'', is_active:true });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function load(){
    setError('');
    try {
      setRows(await fetchMasterValues('', false));
    } catch (err) {
      setError(err.message || 'Unable to load master data.');
    }
  }

  useEffect(()=>{ load().catch(console.error); },[]);

  async function submit(e){
    e.preventDefault();
    setError('');
    setNotice('');
    if (!value.trim()) {
      setError('Value is required.');
      return;
    }
    try {
      await createMasterValue({ group_name: groupName, value: value.trim(), code: code.trim(), is_active: isActive });
      setNotice('Value added.');
      setValue(''); setCode(''); setIsActive(true);
      await load();
    } catch (err) {
      setError(err.message || 'Unable to save value.');
    }
  }

  async function saveEdit(e){
    e.preventDefault();
    setError('');
    setNotice('');
    if (!edit.value.trim()) {
      setError('Value is required.');
      return;
    }
    try {
      await updateMasterValue(editingId, { ...edit, value: edit.value.trim(), code: edit.code.trim() });
      setNotice('Value updated.');
      setEditingId(null);
      setEdit({ value:'', code:'', group_name:'', is_active:true });
      await load();
    } catch (err) {
      setError(err.message || 'Unable to update value.');
    }
  }

  const filtered = useMemo(() => rows.filter(r => r.group_name === groupName), [rows, groupName]);

  return <div>
    <section className="section">
      <h1>Master Data</h1>
      <p className="muted">Supporting lookup lists belong here, not in dedicated setup pages. Use this area for shared values like inventory categories, units, and booking channels.</p>
    </section>
    {!!notice && <p className="success-text">{notice}</p>}
    {!!error && <p className="error-text">{error}</p>}
    <div className="grid-30-70">
      <section className="section">
        <h2>Groups</h2>
        <div className="stack">
          {presets.map(g => <button key={g} type="button" className={groupName===g ? 'tab active full-width' : 'tab full-width'} onClick={()=>{ setGroupName(g); setEditingId(null); }}>{g}</button>)}
        </div>
      </section>
      <section className="stack">
        <section className="section">
          <div className="row" style={{justifyContent:'space-between'}}>
            <div>
              <h2>{groupName}</h2>
              <p className="muted">Only manage values here when there is no dedicated setup page.</p>
            </div>
            <span className="badge">{filtered.length}</span>
          </div>
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>List<input list="group-options" value={groupName} onChange={e=>setGroupName(e.target.value)} /></label>
              <datalist id="group-options">{presets.map(g => <option key={g} value={g} />)}</datalist>
              <label>Value<input required value={value} onChange={e=>setValue(e.target.value)} /></label>
              <label>Code<input value={code} onChange={e=>setCode(e.target.value)} placeholder="Optional lookup key" /></label>
              <label>Status<select value={String(isActive)} onChange={e=>setIsActive(e.target.value === 'true')}><option value="true">Active</option><option value="false">Inactive</option></select></label>
            </div>
            <button type="submit">Add value</button>
          </form>
          {groupName === 'inventory_subcategories' && (
            <p className="muted small">Tip: use codes like <strong>category_code_subcategory</strong> so Inventory Items can filter subcategories by parent category.</p>
          )}
        </section>

        <section className="section">
          <table className="table">
            <thead><tr><th>Value</th><th>Code</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {filtered.map(r=><tr key={r.id}>
                <td>{editingId===r.id ? <input value={edit.value} onChange={e=>setEdit(f=>({...f,value:e.target.value}))} /> : r.value}</td>
                <td>{editingId===r.id ? <input value={edit.code || ''} onChange={e=>setEdit(f=>({...f,code:e.target.value}))} /> : (r.code || '')}</td>
                <td>{editingId===r.id ? (
                  <select value={String(edit.is_active)} onChange={e=>setEdit(f=>({...f,is_active:e.target.value === 'true'}))}>
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                ) : (r.is_active ? 'Active' : 'Inactive')}</td>
                <td className="row">
                  {editingId===r.id ? (
                    <>
                      <button type="button" className="secondary" onClick={saveEdit}>Save</button>
                      <button type="button" className="secondary" onClick={()=>setEditingId(null)}>Cancel</button>
                    </>
                  ) : (
                    <>
                      <button type="button" className="secondary" onClick={()=>{setEditingId(r.id); setEdit({ value:r.value || '', code:r.code || '', group_name:r.group_name || '', is_active: !!r.is_active });}}>Edit</button>
                      <button type="button" className="secondary" onClick={async()=>{await deleteMasterValue(r.id); await load();}}>Delete</button>
                    </>
                  )}
                </td>
              </tr>)}
              {!filtered.length && <tr><td colSpan="3" className="muted">No values yet for this group.</td></tr>}
            </tbody>
          </table>
        </section>
      </section>
    </div>
  </div>
}
