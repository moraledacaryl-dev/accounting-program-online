'use client';

import { useEffect, useMemo, useState } from 'react';
import { approveRecord, createRecord, deleteRecord, fetchModuleTaxonomy, getModuleRecords, updateRecord } from '../lib/api';

function scopeTaxonomy(rawTaxonomy, categoryFilter) {
  if (!Array.isArray(categoryFilter) || !categoryFilter.length) {
    return rawTaxonomy || {};
  }
  const scoped = {};
  for (const category of categoryFilter) {
    if (rawTaxonomy?.[category]) scoped[category] = rawTaxonomy[category];
  }
  return scoped;
}

const WORKFLOW_LABELS = {
  draft: 'Draft',
  pending_review: 'For review',
  approved: 'Approved',
  posted: 'Posted',
};

export default function ClientModulePage({
  moduleSlug,
  compactTitle = false,
  categoryFilter = [],
  defaultCategory = '',
  defaultBucket = '',
}) {
  const [taxonomy, setTaxonomy] = useState({});
  const [records, setRecords] = useState([]);
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [selected, setSelected] = useState({ category:'', bucket:'', item:'' });
  const [form, setForm] = useState({
    category: '', bucket: '', item: '', name: '', amount: '', quantity: '', unit: '',
    direction: 'income', payment_method: 'Cash', workflow_status: 'draft', bir_status: 'internal_only',
    channel: '', counterparty: '', transaction_date: '', notes: '', due_date: '', document_ref: '',
  });

  const categories = Object.keys(taxonomy || {});
  const buckets = useMemo(() => Object.keys((taxonomy || {})[form.category] || {}), [taxonomy, form.category]);
  const items = useMemo(() => ((taxonomy || {})[form.category]?.[form.bucket] || []), [taxonomy, form.category, form.bucket]);

  const filterKey = Array.isArray(categoryFilter) ? categoryFilter.join('|') : '';

  async function load() {
    const [tax, recs] = await Promise.all([fetchModuleTaxonomy(moduleSlug), getModuleRecords(moduleSlug, search)]);
    const scoped = scopeTaxonomy(tax || {}, categoryFilter);
    setTaxonomy(scoped);
    setRecords(Array.isArray(recs) ? recs : []);
    if (scoped && !selected.category) {
      const preferredCategory = defaultCategory && scoped[defaultCategory] ? defaultCategory : (Object.keys(scoped)[0] || '');
      const preferredBucket = defaultBucket && scoped[preferredCategory]?.[defaultBucket] ? defaultBucket : (Object.keys(scoped[preferredCategory] || {})[0] || '');
      const i = (scoped[preferredCategory]?.[preferredBucket] || [])[0] || '';
      const c = preferredCategory;
      const b = preferredBucket;
      setSelected({ category:c, bucket:b, item:i });
      setForm(f => ({ ...f, category:c, bucket:b, item:i }));
    }
  }

  useEffect(() => { load().catch(console.error); }, [moduleSlug, filterKey]);
  useEffect(() => {
    if (!categories.length) return;
    const categoryIsValid = categories.includes(form.category);
    if (!categoryIsValid) {
      const nextCategory = defaultCategory && categories.includes(defaultCategory) ? defaultCategory : categories[0];
      const nextBucket = defaultBucket && taxonomy[nextCategory]?.[defaultBucket] ? defaultBucket : (Object.keys(taxonomy[nextCategory] || {})[0] || '');
      const nextItem = (taxonomy[nextCategory]?.[nextBucket] || [])[0] || '';
      setSelected({ category: nextCategory, bucket: nextBucket, item: nextItem });
      setForm((f) => ({ ...f, category: nextCategory, bucket: nextBucket, item: nextItem }));
    }
  }, [categories.join('|'), form.category, defaultCategory, defaultBucket, taxonomy]);

  useEffect(() => {
    if (!form.category) return;
    const scopedBuckets = Object.keys(taxonomy[form.category] || {});
    if (!scopedBuckets.length) return;
    if (!scopedBuckets.includes(form.bucket)) {
      const nextBucket = defaultBucket && scopedBuckets.includes(defaultBucket) ? defaultBucket : scopedBuckets[0];
      const nextItem = (taxonomy[form.category]?.[nextBucket] || [])[0] || '';
      setSelected((s) => ({ ...s, bucket: nextBucket, item: nextItem }));
      setForm((f) => ({ ...f, bucket: nextBucket, item: nextItem }));
    }
  }, [form.category, form.bucket, defaultBucket, taxonomy]);

  useEffect(() => {
    if (!form.category || !form.bucket) return;
    if (!items.length) return;
    if (!items.includes(form.item)) {
      const nextItem = items[0];
      setSelected((s) => ({ ...s, item: nextItem }));
      setForm((f) => ({ ...f, item: nextItem }));
    }
  }, [form.category, form.bucket, form.item, items.join('|')]);

  const filteredRecords = useMemo(() => {
    return records.filter(r => {
      if (selected.category && r.category !== selected.category) return false;
      if (selected.bucket && r.bucket !== selected.bucket) return false;
      return true;
    });
  }, [records, selected]);

  function choose(category, bucket='') {
    const nextBucket = bucket || (Object.keys(taxonomy[category] || {})[0] || '');
    const nextItem = (taxonomy[category]?.[nextBucket] || [])[0] || '';
    setSelected({ category, bucket: nextBucket, item: nextItem });
    setForm(f => ({ ...f, category, bucket: nextBucket, item: nextItem }));
  }

  async function submit(e) {
    e.preventDefault();
    const payload = {
      category: form.category, bucket: form.bucket, item: form.item, name: form.name || form.item,
      amount: Number(form.amount || 0), quantity: Number(form.quantity || 0), unit: form.unit || null,
      direction: form.direction, payment_method: form.payment_method || null,
      workflow_status: form.workflow_status, bir_status: form.bir_status, channel: form.channel || null,
      counterparty: form.counterparty || null, transaction_date: form.transaction_date || null,
      due_date: form.due_date || null, document_ref: form.document_ref || null, notes: form.notes || null, metadata: {},
    };
    if (editingId) await updateRecord(editingId, payload);
    else await createRecord(moduleSlug, payload);

    setEditingId(null);
    setForm(f=>({...f, name:'', amount:'', quantity:'', unit:'', channel:'', counterparty:'', transaction_date:'', notes:'', due_date:'', document_ref:''}));
    await load();
  }

  function editRow(r) {
    setEditingId(r.id);
    setSelected({ category:r.category || '', bucket:r.bucket || '', item:r.item || '' });
    setForm({
      category: r.category || '', bucket: r.bucket || '', item: r.item || '', name: r.name || '',
      amount: r.amount ?? '', quantity: r.quantity ?? '', unit: r.unit || '', direction: r.direction || 'income',
      payment_method: r.payment_method || 'Cash', workflow_status: r.workflow_status || 'draft',
      bir_status: r.bir_status || 'internal_only', channel: r.channel || '', counterparty: r.counterparty || '',
      transaction_date: r.transaction_date || '', notes: r.notes || '', due_date: r.due_date || '', document_ref: r.document_ref || '',
    });
  }

  return (
    <div className="workspace-grid">
      <aside className="section taxonomy-panel">
        {!compactTitle && <h2>{moduleSlug}</h2>}
        <div className="muted small">
          Choose a category or subcategory on the left. The detailed type stays in the form.
          {categoryFilter.length > 0 ? ` View is scoped to: ${categoryFilter.join(', ')}.` : ''}
        </div>
        <div className="stack taxonomy-tree">
          {categories.map(category => (
            <div key={category} className="taxonomy-node">
              <button type="button" className={selected.category===category ? 'taxonomy-btn active' : 'taxonomy-btn'} onClick={()=>choose(category)}>{category}</button>
              <div className="bucket-list">
                {Object.keys(taxonomy[category] || {}).map(bucket => (
                  <div key={bucket}>
                    <button type="button" className={selected.category===category && selected.bucket===bucket ? 'taxonomy-subbtn active' : 'taxonomy-subbtn'} onClick={()=>choose(category, bucket)}>{bucket}</button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <section className="section">
        <div className="row" style={{justifyContent:'space-between'}}>
          <h2>{editingId ? 'Edit Record' : 'New Record'}</h2>
          <span className="badge">{selected.category || 'No category'}</span>
        </div>
        <form onSubmit={submit}>
          <div className="form-grid">
            <label>Category<select value={form.category} onChange={(e)=>setForm(f=>({...f, category:e.target.value, bucket:'', item:''}))}>{categories.map(c=><option key={c} value={c}>{c}</option>)}</select></label>
            <label>Subcategory<select value={form.bucket} onChange={(e)=>setForm(f=>({...f, bucket:e.target.value, item:''}))}>{buckets.map(c=><option key={c} value={c}>{c}</option>)}</select></label>
            <label>Detail<select value={form.item} onChange={(e)=>setForm(f=>({...f, item:e.target.value}))}>{items.map(c=><option key={c} value={c}>{c}</option>)}</select></label>
            <label>Title<input value={form.name} onChange={(e)=>setForm(f=>({...f, name:e.target.value}))} placeholder="Optional custom title" /></label>
            <label>Flow<select value={form.direction} onChange={(e)=>setForm(f=>({...f, direction:e.target.value}))}><option value="income">Income</option><option value="expense">Expense</option><option value="asset">Asset</option><option value="liability">Liability</option><option value="neutral">Neutral</option></select></label>
            <label>Amount<input type="number" step="0.01" inputMode="decimal" value={form.amount} onChange={(e)=>setForm(f=>({...f, amount:e.target.value}))} /></label>
            <label>Quantity<input type="number" step="0.01" inputMode="decimal" value={form.quantity} onChange={(e)=>setForm(f=>({...f, quantity:e.target.value}))} /></label>
            <label>Unit<input value={form.unit} onChange={(e)=>setForm(f=>({...f, unit:e.target.value}))} /></label>
            <label>Payment<input value={form.payment_method} onChange={(e)=>setForm(f=>({...f, payment_method:e.target.value}))} placeholder="Cash, Card, GCash..." /></label>
            <label>Channel<input value={form.channel} onChange={(e)=>setForm(f=>({...f, channel:e.target.value}))} /></label>
            <label>Counterparty<input value={form.counterparty} onChange={(e)=>setForm(f=>({...f, counterparty:e.target.value}))} /></label>
            <label>Date<input type="date" value={form.transaction_date} onChange={(e)=>setForm(f=>({...f, transaction_date:e.target.value}))} /></label>
            <label>Due<input type="date" value={form.due_date} onChange={(e)=>setForm(f=>({...f, due_date:e.target.value}))} /></label>
            <label>Reference<input value={form.document_ref} onChange={(e)=>setForm(f=>({...f, document_ref:e.target.value}))} /></label>
            <label>Status<select value={form.workflow_status} onChange={(e)=>setForm(f=>({...f, workflow_status:e.target.value}))}><option value="draft">Draft</option><option value="pending_review">For review</option><option value="approved">Approved</option><option value="posted">Posted</option></select></label>
            <label>BIR<select value={form.bir_status} onChange={(e)=>setForm(f=>({...f, bir_status:e.target.value}))}><option value="internal_only">Internal only</option><option value="ready_for_bir">Ready for BIR</option><option value="needs_review">Needs review</option><option value="posted_to_bir">Posted to BIR</option></select></label>
          </div>
          <label>Notes<textarea value={form.notes} onChange={(e)=>setForm(f=>({...f, notes:e.target.value}))} /></label>
          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Record' : 'Save Record'}</button>
            {editingId && <button type="button" className="secondary" onClick={()=>{setEditingId(null); setForm(f=>({...f, name:'', amount:'', quantity:'', unit:'', notes:'', channel:'', counterparty:'', transaction_date:'', due_date:'', document_ref:''}));}}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <div className="row" style={{justifyContent:'space-between'}}>
          <div>
            <h2>Records</h2>
            <div className="small muted">Showing {filteredRecords.length} matching records</div>
          </div>
          <div className="row wrap">
            <input type="search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search records" />
            <button className="secondary" onClick={()=>load().catch(console.error)}>Search</button>
          </div>
        </div>
        <table className="table">
          <thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Amount</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {filteredRecords.map(r=>(
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{r.name}</td>
                <td>{r.category} / {r.bucket} / {r.item}</td>
                <td>{Number(r.amount||0).toLocaleString()}</td>
                <td>{WORKFLOW_LABELS[r.workflow_status] || r.workflow_status}</td>
                <td className="row wrap">
                  <button className="secondary" onClick={()=>editRow(r)}>Edit</button>
                  <button className="secondary" onClick={async()=>{await approveRecord(r.id,true); await load();}}>Approve</button>
                  <button className="secondary" onClick={async()=>{if(confirm('Delete record?')) {await deleteRecord(r.id); await load();}}}>Delete</button>
                </td>
              </tr>
            ))}
            {!filteredRecords.length && <tr><td colSpan="6" className="muted">No records match this taxonomy selection yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
