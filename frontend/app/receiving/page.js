'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  createReceivingRecord,
  deleteReceivingRecord,
  fetchInventoryItems,
  fetchNextCodePreview,
  fetchPurchaseOrders,
  fetchReceivingRecords,
  fetchSuppliersEntity,
  updateReceivingRecord,
  updateReceivingStatus,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const EMPTY_LINE = {
  purchase_order_line_id: '',
  inventory_item_id: '',
  description: '',
  quantity_received: '0',
  unit: '',
  unit_cost: '0',
  notes: '',
};

const EMPTY_FORM = {
  receiving_no: '',
  receiving_date: '',
  supplier_id: '',
  purchase_order_id: '',
  status: 'draft',
  reference_no: '',
  post_to_stock: true,
  auto_create_payable: true,
  notes: '',
  lines: [{ ...EMPTY_LINE }],
};

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function ReceivingPage() {
  const [rows, setRows] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [items, setItems] = useState([]);

  const [statusFilter, setStatusFilter] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [receivingData, supplierData, poData, itemData] = await Promise.all([
      fetchReceivingRecords({ status: statusFilter || undefined }),
      fetchSuppliersEntity({ active_only: true }),
      fetchPurchaseOrders(),
      fetchInventoryItems(),
    ]);
    setRows(Array.isArray(receivingData) ? receivingData : []);
    setSuppliers(Array.isArray(supplierData) ? supplierData : []);
    setPurchaseOrders(Array.isArray(poData) ? poData : []);
    setItems(Array.isArray(itemData) ? itemData : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('receiving');
      setForm((prev) => ({ ...prev, receiving_no: preview?.code || prev.receiving_no || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load receiving records.'));
  }, [statusFilter]);

  useEffect(() => {
    hydrateNewCode();
  }, []);

  const poById = useMemo(() => {
    const map = new Map();
    for (const row of purchaseOrders) map.set(row.id, row);
    return map;
  }, [purchaseOrders]);

  function updateLine(index, patch) {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    }));
  }

  function addLine() {
    setForm((prev) => ({ ...prev, lines: [...prev.lines, { ...EMPTY_LINE }] }));
  }

  function removeLine(index) {
    setForm((prev) => {
      const next = prev.lines.filter((_, i) => i !== index);
      return {
        ...prev,
        lines: next.length ? next : [{ ...EMPTY_LINE }],
      };
    });
  }

  function isSubmittable() {
    const hasLines = form.lines.some((line) => (line.inventory_item_id || line.description) && Number(line.quantity_received || 0) > 0);
    if (form.status === 'posted') return hasLines;
    return true;
  }

  function populateLinesFromPo(poId) {
    const po = poById.get(Number(poId));
    if (!po) return;
    setForm((prev) => ({
      ...prev,
      purchase_order_id: String(po.id),
      supplier_id: po.supplier_id ? String(po.supplier_id) : prev.supplier_id,
      receiving_date: prev.receiving_date || po.po_date || prev.receiving_date,
      lines: (po.lines || [])
        .map((line) => {
          const ordered = Number(line.quantity_ordered || 0);
          const received = Number(line.quantity_received || 0);
          const remaining = Math.max(0, ordered - received);
          if (remaining <= 0) return null;
          return {
            purchase_order_line_id: line.id ? String(line.id) : '',
            inventory_item_id: line.inventory_item_id ? String(line.inventory_item_id) : '',
            description: line.description || line.inventory_item_name || '',
            quantity_received: String(remaining),
            unit: line.unit || '',
            unit_cost: String(line.unit_cost ?? '0'),
            notes: line.notes || '',
          };
        })
        .filter(Boolean),
    }));
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        receiving_no: form.receiving_no || null,
        receiving_date: form.receiving_date || null,
        supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
        purchase_order_id: form.purchase_order_id ? Number(form.purchase_order_id) : null,
        status: form.status,
        reference_no: form.reference_no || null,
        notes: form.notes || null,
        post_to_stock: !!form.post_to_stock,
        auto_create_payable: !!form.auto_create_payable,
        lines: form.lines
          .map((line, idx) => ({
            purchase_order_line_id: line.purchase_order_line_id ? Number(line.purchase_order_line_id) : null,
            inventory_item_id: line.inventory_item_id ? Number(line.inventory_item_id) : null,
            description: line.description || null,
            quantity_received: Number(line.quantity_received || 0),
            unit: line.unit || null,
            unit_cost: Number(line.unit_cost || 0),
            notes: line.notes || null,
            sort_order: idx,
          }))
          .filter((line) => line.inventory_item_id || line.description),
      };

      if (payload.status === 'posted' && !payload.lines.length) {
        setError('Receiving cannot be posted without lines.');
        return;
      }

      if (editingId) {
        await updateReceivingRecord(editingId, payload);
        setNotice('Receiving record updated.');
      } else {
        await createReceivingRecord(payload);
        setNotice('Receiving record created.');
      }

      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save receiving record.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      receiving_no: row.receiving_no || '',
      receiving_date: row.receiving_date || '',
      supplier_id: row.supplier_id ? String(row.supplier_id) : '',
      purchase_order_id: row.purchase_order_id ? String(row.purchase_order_id) : '',
      status: row.status || 'draft',
      reference_no: row.reference_no || '',
      post_to_stock: row.status === 'posted' ? true : false,
      auto_create_payable: true,
      notes: row.notes || '',
      lines: (row.lines || []).map((line) => ({
        purchase_order_line_id: line.purchase_order_line_id ? String(line.purchase_order_line_id) : '',
        inventory_item_id: line.inventory_item_id ? String(line.inventory_item_id) : '',
        description: line.description || '',
        quantity_received: String(line.quantity_received ?? '0'),
        unit: line.unit || '',
        unit_cost: String(line.unit_cost ?? '0'),
        notes: line.notes || '',
      })) || [{ ...EMPTY_LINE }],
    });
  }

  async function removeRow(row) {
    if (!window.confirm(`Delete receiving ${row.receiving_no || row.id}?`)) return;
    setError('');
    try {
      await deleteReceivingRecord(row.id);
      setNotice('Receiving record deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete receiving record.');
    }
  }

  async function setStatus(row, status) {
    setError('');
    try {
      if (status === 'posted' && !(row.lines || []).length) {
        setError('Receiving cannot be posted without lines.');
        return;
      }
      await updateReceivingStatus(row.id, { status, notes: `Status changed to ${status}`, auto_create_payable: true });
      setNotice(`Receiving ${row.receiving_no || row.id} marked as ${status}.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update receiving status.');
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Receiving</h1>
            <p className="muted">Post deliveries, update stock with FIFO batches, and optionally create supplier payables.</p>
          </div>
          <label style={{ minWidth: 200 }}>
            Status Filter
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="draft">draft</option>
              <option value="posted">posted</option>
              <option value="reversed">reversed</option>
            </select>
          </label>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? `Edit Receiving #${editingId}` : 'New Receiving'}</h2>
        <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
            <label>Receiving No<input value={form.receiving_no} onChange={(e) => setForm((prev) => ({ ...prev, receiving_no: e.target.value }))} placeholder="Auto-generated if blank" /></label>
            <label>Receiving Date<input type="date" value={form.receiving_date} onChange={(e) => setForm((prev) => ({ ...prev, receiving_date: e.target.value }))} /></label>
            <label>Supplier
              <select value={form.supplier_id} onChange={(e) => setForm((prev) => ({ ...prev, supplier_id: e.target.value }))}>
                <option value="">Select</option>
                {suppliers.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
            <label>Purchase Order
              <select value={form.purchase_order_id} onChange={(e) => populateLinesFromPo(e.target.value)}>
                <option value="">None</option>
                {purchaseOrders.map((row) => (
                  <option key={row.id} value={row.id}>{row.po_no} · {row.supplier_name || '-'} · {row.status}</option>
                ))}
              </select>
            </label>
            <label>Status
              <select value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}>
                <option value="draft">draft</option>
                <option value="posted">posted</option>
                <option value="reversed">reversed</option>
              </select>
            </label>
            <label>Reference No<input value={form.reference_no} onChange={(e) => setForm((prev) => ({ ...prev, reference_no: e.target.value }))} /></label>
            <label>Post to Stock
              <select value={String(form.post_to_stock)} onChange={(e) => setForm((prev) => ({ ...prev, post_to_stock: e.target.value === 'true' }))}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label>Create Supplier Bill
              <select value={String(form.auto_create_payable)} onChange={(e) => setForm((prev) => ({ ...prev, auto_create_payable: e.target.value === 'true' }))}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
          </div>

          <div className="section" style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h3>Receiving Lines</h3>
              <button type="button" className="secondary" onClick={addLine}>Add Line</button>
            </div>
            {form.lines.map((line, index) => (
              <div key={`line-${index}`} className="form-grid" style={{ marginTop: 10 }} data-enter-context="line-item">
                <label>Inventory Item
                  <select value={line.inventory_item_id} onChange={(e) => {
                    const selected = items.find((item) => String(item.id) === e.target.value);
                    updateLine(index, {
                      inventory_item_id: e.target.value,
                      description: selected ? selected.name : line.description,
                      unit: selected ? (selected.unit || line.unit) : line.unit,
                    });
                  }}>
                    <option value="">Select</option>
                    {items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Description<input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} /></label>
                <label>Qty Received<input type="number" min="0" step="0.01" value={line.quantity_received} onChange={(e) => updateLine(index, { quantity_received: e.target.value })} /></label>
                <label>Unit<input value={line.unit} onChange={(e) => updateLine(index, { unit: e.target.value })} /></label>
                <label>Unit Cost<input type="number" min="0" step="0.01" value={line.unit_cost} onChange={(e) => updateLine(index, { unit_cost: e.target.value })} /></label>
                <label>Notes<input value={line.notes} onChange={(e) => updateLine(index, { notes: e.target.value })} /></label>
                <div className="row" style={{ alignItems: 'end' }}>
                  <button type="button" className="secondary" onClick={() => removeLine(index)}>Remove</button>
                </div>
              </div>
            ))}
          </div>

          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>

          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Receiving' : 'Create Receiving'}</button>
            {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Receiving List</h2>
        <table className="table">
          <thead><tr><th>No</th><th>Date</th><th>Supplier</th><th>PO</th><th>Status</th><th>Total</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.receiving_no}</td>
                <td>{row.receiving_date || '-'}</td>
                <td>{row.supplier_name || '-'}</td>
                <td>{row.purchase_order_no || '-'}</td>
                <td>{row.status}</td>
                <td>{php(row.total_amount || 0)}</td>
                <td className="row wrap">
                  <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'posted')}>Post</button>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'reversed')}>Reverse</button>
                  <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="7" className="muted">No receiving records yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
