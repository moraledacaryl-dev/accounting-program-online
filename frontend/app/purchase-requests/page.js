'use client';

import { useEffect, useState } from 'react';
import {
  convertPurchaseRequestToPo,
  createPurchaseRequest,
  deletePurchaseRequest,
  fetchInventoryItems,
  fetchNextCodePreview,
  fetchPurchaseRequests,
  fetchSuppliersEntity,
  updatePurchaseRequest,
  updatePurchaseRequestStatus,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_LINE = {
  inventory_item_id: '',
  description: '',
  quantity: '1',
  unit: '',
  estimated_unit_cost: '0',
  notes: '',
};

const EMPTY_FORM = {
  request_no: '',
  request_date: '',
  needed_by_date: '',
  department: '',
  supplier_id: '',
  status: 'draft',
  notes: '',
  lines: [{ ...EMPTY_LINE }],
};

export default function PurchaseRequestsPage() {
  const [suppliers, setSuppliers] = useState([]);
  const [items, setItems] = useState([]);
  const [rows, setRows] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [statusFilter, setStatusFilter] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [prData, supplierData, itemData] = await Promise.all([
      fetchPurchaseRequests({ status: statusFilter || undefined }),
      fetchSuppliersEntity({ active_only: true }),
      fetchInventoryItems(),
    ]);
    setRows(Array.isArray(prData) ? prData : []);
    setSuppliers(Array.isArray(supplierData) ? supplierData : []);
    setItems(Array.isArray(itemData) ? itemData : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('purchase_request');
      setForm((prev) => ({ ...prev, request_no: preview?.code || prev.request_no || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load purchase requests.'));
  }, [statusFilter]);

  useEffect(() => {
    hydrateNewCode();
  }, []);

  function updateLine(index, patch) {
    setForm((f) => ({
      ...f,
      lines: f.lines.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    }));
  }

  function addLine() {
    setForm((f) => ({ ...f, lines: [...f.lines, { ...EMPTY_LINE }] }));
  }

  function removeLine(index) {
    setForm((f) => ({
      ...f,
      lines: f.lines.filter((_, i) => i !== index).length ? f.lines.filter((_, i) => i !== index) : [{ ...EMPTY_LINE }],
    }));
  }

  function isSubmittable() {
    return form.lines.some((line) => (line.inventory_item_id || line.description) && Number(line.quantity || 0) > 0);
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        request_no: form.request_no || null,
        request_date: form.request_date || null,
        needed_by_date: form.needed_by_date || null,
        department: form.department || null,
        supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
        status: form.status,
        notes: form.notes || null,
        lines: form.lines
          .map((line, idx) => ({
            inventory_item_id: line.inventory_item_id ? Number(line.inventory_item_id) : null,
            description: line.description || null,
            quantity: Number(line.quantity || 0),
            unit: line.unit || null,
            estimated_unit_cost: Number(line.estimated_unit_cost || 0),
            notes: line.notes || null,
            sort_order: idx,
          }))
          .filter((line) => line.inventory_item_id || line.description),
      };

      if (!payload.lines.length) {
        setError('Add at least one PR line.');
        return;
      }

      if (editingId) {
        await updatePurchaseRequest(editingId, payload);
        setNotice('Purchase request updated.');
      } else {
        await createPurchaseRequest(payload);
        setNotice('Purchase request created.');
      }
      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save purchase request.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      request_no: row.request_no || '',
      request_date: row.request_date || '',
      needed_by_date: row.needed_by_date || '',
      department: row.department || '',
      supplier_id: row.supplier_id ? String(row.supplier_id) : '',
      status: row.status || 'draft',
      notes: row.notes || '',
      lines: (row.lines || []).map((line) => ({
        inventory_item_id: line.inventory_item_id ? String(line.inventory_item_id) : '',
        description: line.description || '',
        quantity: String(line.quantity ?? '1'),
        unit: line.unit || '',
        estimated_unit_cost: String(line.estimated_unit_cost ?? '0'),
        notes: line.notes || '',
      })) || [{ ...EMPTY_LINE }],
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete purchase request ${row.request_no || row.id}?`)) return;
    setError('');
    try {
      await deletePurchaseRequest(row.id);
      setNotice('Purchase request deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete purchase request.');
    }
  }

  async function setStatus(row, status) {
    setError('');
    try {
      await updatePurchaseRequestStatus(row.id, { status });
      setNotice(`PR ${row.request_no || row.id} marked as ${status}.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update PR status.');
    }
  }

  async function convertToPo(row) {
    setError('');
    try {
      await convertPurchaseRequestToPo(row.id);
      setNotice(`PR ${row.request_no || row.id} converted to PO.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to convert PR to PO.');
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Purchase Requests</h1>
            <p className="muted">Create PR headers and lines, then submit/approve/convert to PO.</p>
          </div>
          <label style={{ minWidth: 200 }}>Status Filter
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="draft">draft</option>
              <option value="submitted">submitted</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
              <option value="converted_to_po">converted_to_po</option>
            </select>
          </label>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? `Edit PR #${editingId}` : 'New Purchase Request'}</h2>
        <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
            <label>Request No<input value={form.request_no} onChange={(e) => setForm((f) => ({ ...f, request_no: e.target.value }))} placeholder="Auto-generated if blank" /></label>
            <label>Request Date<input type="date" value={form.request_date} onChange={(e) => setForm((f) => ({ ...f, request_date: e.target.value }))} /></label>
            <label>Needed By<input type="date" value={form.needed_by_date} onChange={(e) => setForm((f) => ({ ...f, needed_by_date: e.target.value }))} /></label>
            <label>Department<input value={form.department} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))} /></label>
            <label>Supplier
              <select value={form.supplier_id} onChange={(e) => setForm((f) => ({ ...f, supplier_id: e.target.value }))}>
                <option value="">Select</option>
                {suppliers.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
            <label>Status
              <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
                <option value="draft">draft</option>
                <option value="submitted">submitted</option>
                <option value="approved">approved</option>
                <option value="rejected">rejected</option>
                <option value="converted_to_po">converted_to_po</option>
              </select>
            </label>
          </div>

          <div className="section" style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h3>Lines</h3>
              <button type="button" className="secondary" onClick={addLine}>Add Line</button>
            </div>
            {form.lines.map((line, index) => (
              <div key={index} className="form-grid" style={{ marginTop: 10 }} data-enter-context="line-item">
                <label>Inventory Item
                  <select
                    value={line.inventory_item_id}
                    onChange={(e) => {
                      const selected = items.find((item) => String(item.id) === e.target.value);
                      updateLine(index, {
                        inventory_item_id: e.target.value,
                        description: selected ? selected.name : line.description,
                        unit: selected ? (selected.unit || line.unit) : line.unit,
                      });
                    }}
                  >
                    <option value="">Select</option>
                    {items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Description<input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} /></label>
                <label>Qty<input type="number" min="0" step="0.01" value={line.quantity} onChange={(e) => updateLine(index, { quantity: e.target.value })} /></label>
                <label>Unit<input value={line.unit} onChange={(e) => updateLine(index, { unit: e.target.value })} /></label>
                <label>Est. Unit Cost<input type="number" min="0" step="0.01" value={line.estimated_unit_cost} onChange={(e) => updateLine(index, { estimated_unit_cost: e.target.value })} /></label>
                <label>Notes<input value={line.notes} onChange={(e) => updateLine(index, { notes: e.target.value })} /></label>
                <div className="row" style={{ alignItems: 'end' }}>
                  <button type="button" className="secondary" onClick={() => removeLine(index)}>Remove</button>
                </div>
              </div>
            ))}
          </div>

          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>

          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Purchase Request' : 'Create Purchase Request'}</button>
            {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Purchase Request List</h2>
        <table className="table">
          <thead><tr><th>No</th><th>Date</th><th>Supplier</th><th>Status</th><th>Estimated Total</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.request_no}</td>
                <td>{row.request_date || '-'}</td>
                <td>{row.supplier_name || '-'}</td>
                <td>{row.status}</td>
                <td>{Number(row.estimated_total || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td className="row wrap">
                  <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'submitted')}>Submit</button>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'approved')}>Approve</button>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'rejected')}>Reject</button>
                  <button type="button" className="secondary" onClick={() => convertToPo(row)}>Convert to PO</button>
                  <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="6" className="muted">No purchase requests yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
