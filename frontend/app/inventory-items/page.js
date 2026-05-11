'use client';
import { useEffect, useMemo, useState } from 'react';
import { createInventoryItem, deleteInventoryItem, fetchInventoryItems, fetchMasterValues, updateInventoryItem } from '../../lib/api';

export default function InventoryItemsPage() {
  const [rows, setRows] = useState([]);
  const [masterRows, setMasterRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ name: '', category_name: '', subcategory_name: '', unit: 'pcs', reorder_level: '0', notes: '' });
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      const [items, masterValues] = await Promise.all([fetchInventoryItems(), fetchMasterValues('', true)]);
      setRows(items);
      setMasterRows(masterValues);
    } catch (err) {
      setError(err.message || 'Unable to load inventory items.');
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!form.name.trim()) {
      setError('Inventory item name is required.');
      return;
    }
    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        category_name: form.category_name || '',
        subcategory_name: form.subcategory_name || '',
        unit: form.unit || '',
        reorder_level: Number(form.reorder_level || 0),
        notes: form.notes.trim(),
      };
      if (editingId) {
        await updateInventoryItem(editingId, payload);
        setNotice('Inventory item updated.');
      } else {
        await createInventoryItem(payload);
        setNotice('Inventory item added.');
      }
      setEditingId(null);
      setForm({ name: '', category_name: '', subcategory_name: '', unit: 'pcs', reorder_level: '0', notes: '' });
      await load();
    } catch (err) {
      setError(err.message || 'Unable to save inventory item.');
    }
  }

  const inventoryCategories = useMemo(() => masterRows.filter((row) => row.group_name === 'inventory_categories'), [masterRows]);
  const inventorySubcategories = useMemo(() => masterRows.filter((row) => row.group_name === 'inventory_subcategories'), [masterRows]);
  const unitsOfMeasure = useMemo(() => masterRows.filter((row) => row.group_name === 'units_of_measure'), [masterRows]);

  const selectedCategory = useMemo(() => inventoryCategories.find((row) => row.value === form.category_name) || null, [inventoryCategories, form.category_name]);

  const filteredSubcategories = useMemo(() => {
    if (!form.category_name) return inventorySubcategories;
    if (selectedCategory?.code) {
      return inventorySubcategories.filter((row) => row.code && row.code.startsWith(`${selectedCategory.code}_`));
    }
    return inventorySubcategories;
  }, [inventorySubcategories, selectedCategory, form.category_name]);

  const otherSubcategories = useMemo(() => {
    if (!form.category_name || !selectedCategory?.code) return [];
    return inventorySubcategories.filter((row) => !(row.code && row.code.startsWith(`${selectedCategory.code}_`)));
  }, [inventorySubcategories, selectedCategory, form.category_name]);

  const unitOptions = useMemo(() => {
    const values = new Set(unitsOfMeasure.map((row) => row.value).filter(Boolean));
    return Array.from(values).sort();
  }, [unitsOfMeasure]);

  return (
    <div>
      <section className="section">
        <h1>Inventory Items</h1>
        <p className="muted">Create inventory items with a controlled category, subcategory, and purchase unit. Subcategories are surfaced based on the selected category.</p>
      </section>

      {!!notice && <p className="success-text">{notice}</p>}
      {!!error && <p className="error-text">{error}</p>}

      <div className="grid">
        <section className="section">
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>Name<input value={form.name} onChange={e => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
              <label>Category<select value={form.category_name} onChange={e => setForm((f) => ({ ...f, category_name: e.target.value, subcategory_name: '' }))}>
                <option value="">Select category...</option>
                {inventoryCategories.map((row) => <option key={row.id} value={row.value}>{row.value}</option>)}
              </select></label>
              {selectedCategory?.code ? (
                <p className="muted small">Filtering subcategories by category code: {selectedCategory.code}_*</p>
              ) : form.category_name ? (
                <p className="muted small">This category has no code yet. Add a code in Master Data to enable linked subcategory filtering.</p>
              ) : (
                <p className="muted small">Choose a category first to narrow the subcategory list.</p>
              )}
              <label>Subcategory<select value={form.subcategory_name} onChange={e => setForm((f) => ({ ...f, subcategory_name: e.target.value }))}>
                <option value="">Select subcategory...</option>
                {selectedCategory?.code && filteredSubcategories.length > 0 && (
                  <optgroup label="Linked subcategories">
                    {filteredSubcategories.map((row) => <option key={row.id} value={row.value}>{row.value}</option>)}
                  </optgroup>
                )}
                {selectedCategory?.code && otherSubcategories.length > 0 && (
                  <optgroup label="Other subcategories">
                    {otherSubcategories.map((row) => <option key={row.id} value={row.value}>{row.value}</option>)}
                  </optgroup>
                )}
                {!selectedCategory?.code && filteredSubcategories.map((row) => <option key={row.id} value={row.value}>{row.value}</option>)}
              </select></label>
              <label>Unit<select value={form.unit} onChange={e => setForm((f) => ({ ...f, unit: e.target.value }))}>
                <option value="">Select unit...</option>
                {unitOptions.map((row) => <option key={row} value={row}>{row}</option>)}
              </select></label>
              <label>Reorder level<input type="number" step="0.01" value={form.reorder_level} onChange={e => setForm((f) => ({ ...f, reorder_level: e.target.value }))} /></label>
              <label>Notes<textarea value={form.notes} onChange={e => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            </div>
            <button type="submit">{editingId ? 'Update item' : 'Save item'}</button>
          </form>
        </section>

        <section className="section">
          <table className="table">
            <thead>
              <tr><th>Name</th><th>Category</th><th>Subcategory</th><th>Unit</th><th>Reorder</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>{r.category_name || '-'}</td>
                  <td>{r.subcategory_name || '-'}</td>
                  <td>{r.unit || '-'}</td>
                  <td>{r.reorder_level || '0'}</td>
                  <td className="row">
                    <button className="secondary" onClick={() => {
                      setEditingId(r.id);
                      setForm({
                        name: r.name,
                        category_name: r.category_name || '',
                        subcategory_name: r.subcategory_name || '',
                        unit: r.unit || '',
                        reorder_level: String(r.reorder_level || 0),
                        notes: r.notes || '',
                      });
                    }}>
                      Edit
                    </button>
                    <button className="secondary" onClick={async () => { if (confirm('Delete item?')) { await deleteInventoryItem(r.id); await load(); } }}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr><td colSpan="6" className="muted">No inventory items yet. Create one to track stock.</td></tr>
              )}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}
