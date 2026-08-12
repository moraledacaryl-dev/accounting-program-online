'use client';

import { useEffect, useMemo, useState } from 'react';
import { useConfirmAction } from '../../components/ConfirmActionProvider';
import { createTaxonomyNode, deleteTaxonomyNode, fetchTaxonomyNodes, updateTaxonomyNode } from '../../lib/api';

const EMPTY_FORM = {
  module_slug: 'rooms',
  module_name: 'Rooms',
  category: 'Revenue',
  bucket: 'Direct Bookings',
  item: 'Walk-in',
  is_active: true,
};

export default function TaxonomyAdminPage() {
  const confirmAction = useConfirmAction();
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [moduleFilter, setModuleFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function load() {
    const data = await fetchTaxonomyNodes();
    setRows(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Failed to load taxonomy.'));
  }, []);

  const modules = useMemo(() => {
    const map = new Map();
    for (const row of rows) {
      const key = row.module_slug || 'other';
      if (!map.has(key)) map.set(key, { slug: key, name: row.module_name || key, total: 0, active: 0 });
      const entry = map.get(key);
      entry.total += 1;
      if (row.is_active) entry.active += 1;
    }
    return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [rows]);

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (moduleFilter !== 'all' && row.module_slug !== moduleFilter) return false;
      if (!q) return true;
      return [row.module_name, row.category, row.bucket, row.item]
        .some((value) => String(value || '').toLowerCase().includes(q));
    });
  }, [rows, moduleFilter, search]);

  function resetForm() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      module_slug: row.module_slug,
      module_name: row.module_name,
      category: row.category,
      bucket: row.bucket,
      item: row.item,
      is_active: row.is_active,
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    setNotice('');
    try {
      if (editingId) {
        await updateTaxonomyNode(editingId, form);
        setNotice('Taxonomy node updated.');
      } else {
        await createTaxonomyNode(form);
        setNotice('Taxonomy node added.');
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save taxonomy node.');
    }
  }

  return (
    <div className="stack">
      <section className="section" style={{ paddingBottom: 14 }}>
        <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>Taxonomy Administration</h1>
            <p className="muted">Maintain the classification tree used across accounting workspaces.</p>
          </div>
          <div className="row wrap" aria-label="Taxonomy summary">
            <span className="badge">{rows.length} nodes</span>
            <span className="badge">{modules.length} modules</span>
          </div>
        </div>
        {!!notice && <p className="success-text" style={{ marginTop: 10 }}>{notice}</p>}
        {!!error && <p className="error-text" style={{ marginTop: 10 }}>{error}</p>}
      </section>

      <div className="grid-30-70" style={{ alignItems: 'start' }}>
        <aside className="section" style={{ position: 'sticky', top: 76, padding: 12 }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
            <h2 style={{ margin: 0 }}>Modules</h2>
            <button type="button" className="secondary" onClick={() => setModuleFilter('all')}>All</button>
          </div>
          <div className="stack" style={{ gap: 6 }}>
            {modules.map((module) => (
              <button
                key={module.slug}
                type="button"
                className={moduleFilter === module.slug ? 'tab active full-width role-chip' : 'tab full-width role-chip'}
                onClick={() => setModuleFilter(module.slug)}
              >
                <span style={{ textAlign: 'left' }}>{module.name}</span>
                <span className="small muted">{module.active}/{module.total}</span>
              </button>
            ))}
            {!modules.length && <p className="muted small">No taxonomy modules yet.</p>}
          </div>
        </aside>

        <main className="stack">
          <section className="section">
            <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div>
                <h2 style={{ marginBottom: 2 }}>{editingId ? 'Edit taxonomy node' : 'Add taxonomy node'}</h2>
                <p className="small muted">Module → category → bucket → item</p>
              </div>
              {editingId && <button type="button" className="secondary" onClick={resetForm}>Cancel edit</button>}
            </div>

            <form onSubmit={submit}>
              <div className="form-grid">
                <label>Module Slug
                  <input required value={form.module_slug} onChange={(e) => setForm((f) => ({ ...f, module_slug: e.target.value.toLowerCase().replace(/\s+/g, '-') }))} />
                </label>
                <label>Module Name
                  <input required value={form.module_name} onChange={(e) => setForm((f) => ({ ...f, module_name: e.target.value }))} />
                </label>
                <label>Category
                  <input required value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))} />
                </label>
                <label>Bucket
                  <input required value={form.bucket} onChange={(e) => setForm((f) => ({ ...f, bucket: e.target.value }))} />
                </label>
                <label>Item
                  <input required value={form.item} onChange={(e) => setForm((f) => ({ ...f, item: e.target.value }))} />
                </label>
                <label>Status
                  <select value={String(form.is_active)} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.value === 'true' }))}>
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                  </select>
                </label>
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
                <button type="submit">{editingId ? 'Save Changes' : 'Add Node'}</button>
              </div>
            </form>
          </section>

          <section className="section" style={{ padding: 0, overflow: 'hidden' }}>
            <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderBottom: '1px solid var(--line)' }}>
              <div>
                <h2 style={{ marginBottom: 2 }}>Classification tree</h2>
                <p className="small muted">{filteredRows.length} visible nodes</p>
              </div>
              <input
                type="search"
                aria-label="Search taxonomy"
                placeholder="Search category, bucket, item…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ maxWidth: 320 }}
              />
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table className="table" style={{ margin: 0 }}>
                <thead>
                  <tr><th>Module</th><th>Category</th><th>Bucket</th><th>Item</th><th>Status</th><th style={{ textAlign: 'right' }}>Actions</th></tr>
                </thead>
                <tbody>
                  {filteredRows.map((row) => (
                    <tr key={row.id}>
                      <td><strong>{row.module_name}</strong><br /><span className="small muted">{row.module_slug}</span></td>
                      <td>{row.category}</td>
                      <td>{row.bucket}</td>
                      <td>{row.item}</td>
                      <td><span className="badge">{row.is_active ? 'Active' : 'Inactive'}</span></td>
                      <td>
                        <div className="row" style={{ justifyContent: 'flex-end' }}>
                          <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                          <button
                            type="button"
                            className="secondary"
                            onClick={async () => {
                              if (await confirmAction({
                                title: `Delete taxonomy node ${row.item}?`,
                                description: 'Records that use this taxonomy may become harder to classify in the workspace.',
                              })) {
                                await deleteTaxonomyNode(row.id);
                                await load();
                              }
                            }}
                          >Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!filteredRows.length && (
                    <tr><td colSpan="6" className="muted">No taxonomy nodes match the current filters.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
