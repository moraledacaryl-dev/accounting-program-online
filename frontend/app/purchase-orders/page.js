'use client';
import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  createPurchaseOrder,
  deletePurchaseOrder,
  fetchInventoryItems,
  fetchNextCodePreview,
  fetchPurchaseOrders,
  fetchPurchaseRequests,
  fetchSuppliersEntity,
  updatePurchaseOrder,
  updatePurchaseOrderStatus,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';
import { useConfirmAction } from '../../components/ConfirmActionProvider';

const EMPTY_LINE = {
  purchase_request_line_id: '',
  inventory_item_id: '',
  description: '',
  quantity_ordered: '1',
  unit: '',
  unit_cost: '0',
  notes: '',
};

const EMPTY_FORM = {
  po_no: '',
  po_date: '',
  supplier_id: '',
  purchase_request_id: '',
  status: 'draft',
  payment_terms: '',
  expected_delivery_date: '',
  notes: '',
  lines: [{ ...EMPTY_LINE }],
};

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PurchaseOrdersPage() {
  const confirmAction = useConfirmAction();
  const [rows, setRows] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [purchaseRequests, setPurchaseRequests] = useState([]);
  const [items, setItems] = useState([]);

  const [statusFilter, setStatusFilter] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [poData, supplierData, prData, itemData] = await Promise.all([
      fetchPurchaseOrders({ status: statusFilter || undefined }),
      fetchSuppliersEntity({ active_only: true }),
      fetchPurchaseRequests(),
      fetchInventoryItems(),
    ]);
    setRows(Array.isArray(poData) ? poData : []);
    setSuppliers(Array.isArray(supplierData) ? supplierData : []);
    setPurchaseRequests(Array.isArray(prData) ? prData : []);
    setItems(Array.isArray(itemData) ? itemData : []);
  }

  async function hydrateNewCode() {
    try {
      const preview = await fetchNextCodePreview('purchase_order');
      setForm((prev) => ({ ...prev, po_no: preview?.code || prev.po_no || '' }));
    } catch {
      // Keep manual fallback.
    }
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load purchase orders.'));
  }, [statusFilter]);

  useEffect(() => {
    hydrateNewCode();
  }, []);

  const prById = useMemo(() => {
    const map = new Map();
    for (const row of purchaseRequests) map.set(row.id, row);
    return map;
  }, [purchaseRequests]);

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
    const hasLines = form.lines.some((line) => (line.inventory_item_id || line.description) && Number(line.quantity_ordered || 0) > 0);
    const needsSupplier = ['issued', 'partially_received', 'fully_received'].includes(form.status);
    return hasLines && (!needsSupplier || Number(form.supplier_id || 0) > 0);
  }

  function populateLinesFromPr(prId) {
    const pr = prById.get(Number(prId));
    if (!pr) return;
    setForm((prev) => ({
      ...prev,
      supplier_id: pr.supplier_id ? String(pr.supplier_id) : prev.supplier_id,
      purchase_request_id: String(pr.id),
      po_date: prev.po_date || pr.request_date || prev.po_date,
      expected_delivery_date: prev.expected_delivery_date || pr.needed_by_date || prev.expected_delivery_date,
      payment_terms: prev.payment_terms || '',
      lines: (pr.lines || []).map((line) => ({
        purchase_request_line_id: line.id ? String(line.id) : '',
        inventory_item_id: line.inventory_item_id ? String(line.inventory_item_id) : '',
        description: line.description || line.inventory_item_name || '',
        quantity_ordered: String(line.quantity ?? '1'),
        unit: line.unit || '',
        unit_cost: String(line.estimated_unit_cost ?? '0'),
        notes: line.notes || '',
      })),
    }));
  }

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        po_no: form.po_no || null,
        po_date: form.po_date || null,
        supplier_id: form.supplier_id ? Number(form.supplier_id) : null,
        purchase_request_id: form.purchase_request_id ? Number(form.purchase_request_id) : null,
        status: form.status,
        payment_terms: form.payment_terms || null,
        expected_delivery_date: form.expected_delivery_date || null,
        notes: form.notes || null,
        lines: form.lines
          .map((line, idx) => ({
            purchase_request_line_id: line.purchase_request_line_id ? Number(line.purchase_request_line_id) : null,
            inventory_item_id: line.inventory_item_id ? Number(line.inventory_item_id) : null,
            description: line.description || null,
            quantity_ordered: Number(line.quantity_ordered || 0),
            unit: line.unit || null,
            unit_cost: Number(line.unit_cost || 0),
            notes: line.notes || null,
            sort_order: idx,
          }))
          .filter((line) => line.inventory_item_id || line.description),
      };

      if (!payload.lines.length) {
        setError('Add at least one PO line.');
        return;
      }

      if ((payload.status === 'issued' || payload.status === 'partially_received' || payload.status === 'fully_received') && !payload.supplier_id) {
        setError('Supplier is required for issued/receiving PO statuses.');
        return;
      }

      if (editingId) {
        await updatePurchaseOrder(editingId, payload);
        setNotice('Purchase order updated.');
      } else {
        await createPurchaseOrder(payload);
        setNotice('Purchase order created.');
      }

      setEditingId(null);
      setForm({ ...EMPTY_FORM });
      await hydrateNewCode();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save purchase order.');
    }
  }

  function editRow(row) {
    setEditingId(row.id);
    setForm({
      po_no: row.po_no || '',
      po_date: row.po_date || '',
      supplier_id: row.supplier_id ? String(row.supplier_id) : '',
      purchase_request_id: row.purchase_request_id ? String(row.purchase_request_id) : '',
      status: row.status || 'draft',
      payment_terms: row.payment_terms || '',
      expected_delivery_date: row.expected_delivery_date || '',
      notes: row.notes || '',
      lines: (row.lines || []).map((line) => ({
        purchase_request_line_id: line.purchase_request_line_id ? String(line.purchase_request_line_id) : '',
        inventory_item_id: line.inventory_item_id ? String(line.inventory_item_id) : '',
        description: line.description || '',
        quantity_ordered: String(line.quantity_ordered ?? '1'),
        unit: line.unit || '',
        unit_cost: String(line.unit_cost ?? '0'),
        notes: line.notes || '',
      })) || [{ ...EMPTY_LINE }],
    });
  }

  async function removeRow(row) {
    if (!await confirmAction({ title: `Delete PO ${row.po_no || row.id}?`, description: 'Only draft purchase orders should be removed. Issued orders should be cancelled.' })) return;
    setError('');
    try {
      await deletePurchaseOrder(row.id);
      setNotice('Purchase order deleted.');
      if (editingId === row.id) {
        setEditingId(null);
        setForm({ ...EMPTY_FORM });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete purchase order.');
    }
  }

  async function setStatus(row, status) {
    setError('');
    try {
      if ((status === 'issued' || status === 'partially_received' || status === 'fully_received') && !row.supplier_id) {
        setError('Cannot issue/receive PO without supplier.');
        return;
      }
      await updatePurchaseOrderStatus(row.id, { status, notes: `Status changed to ${status}` });
      setNotice(`PO ${row.po_no || row.id} marked as ${status}.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update PO status.');
    }
  }

  return (
    <div>
      <LegacyExternalModuleNotice appName="Inventory & Procurement" />
      <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Purchase Orders</h1>
            <p className="muted">Issue and track POs, linked to suppliers, PRs, and receiving progress.</p>
          </div>
          <label style={{ minWidth: 200 }}>
            Status Filter
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All</option>
              <option value="draft">draft</option>
              <option value="issued">issued</option>
              <option value="partially_received">partially_received</option>
              <option value="fully_received">fully_received</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? `Edit PO #${editingId}` : 'New Purchase Order'}</h2>
        <form onSubmit={submit} className="stack" onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
            <label>PO No<input value={form.po_no} onChange={(e) => setForm((prev) => ({ ...prev, po_no: e.target.value }))} placeholder="Auto-generated if blank" /></label>
            <label>PO Date<input type="date" value={form.po_date} onChange={(e) => setForm((prev) => ({ ...prev, po_date: e.target.value }))} /></label>
            <label>Supplier
              <select value={form.supplier_id} onChange={(e) => setForm((prev) => ({ ...prev, supplier_id: e.target.value }))}>
                <option value="">Select</option>
                {suppliers.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
            <label>From Purchase Request
              <select value={form.purchase_request_id} onChange={(e) => { populateLinesFromPr(e.target.value); }}>
                <option value="">None</option>
                {purchaseRequests.map((row) => (
                  <option key={row.id} value={row.id}>{row.request_no} · {row.supplier_name || '-'} · {row.status}</option>
                ))}
              </select>
            </label>
            <label>Status
              <select value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}>
                <option value="draft">draft</option>
                <option value="issued">issued</option>
                <option value="partially_received">partially_received</option>
                <option value="fully_received">fully_received</option>
                <option value="cancelled">cancelled</option>
              </select>
            </label>
            <label>Payment Terms<input value={form.payment_terms} onChange={(e) => setForm((prev) => ({ ...prev, payment_terms: e.target.value }))} placeholder="COD, 30 days" /></label>
            <label>Expected Delivery<input type="date" value={form.expected_delivery_date} onChange={(e) => setForm((prev) => ({ ...prev, expected_delivery_date: e.target.value }))} /></label>
          </div>

          <div className="section" style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h3>Lines</h3>
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
                <label>Qty Ordered<input type="number" min="0" step="0.01" value={line.quantity_ordered} onChange={(e) => updateLine(index, { quantity_ordered: e.target.value })} /></label>
                <label>Unit<input value={line.unit} readOnly={!!line.inventory_item_id} onChange={(e) => updateLine(index, { unit: e.target.value })} /></label>
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
            <button type="submit">{editingId ? 'Update Purchase Order' : 'Create Purchase Order'}</button>
            {editingId && <button type="button" className="secondary" onClick={() => { setEditingId(null); setForm({ ...EMPTY_FORM }); hydrateNewCode(); }}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Purchase Order List</h2>
        <table className="table">
          <thead><tr><th>No</th><th>Date</th><th>Supplier</th><th>Status</th><th>Progress</th><th>Total</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.po_no}</td>
                <td>{row.po_date || '-'}</td>
                <td>{row.supplier_name || '-'}</td>
                <td>{row.status}</td>
                <td>{Number(row.progress_received_qty || 0).toLocaleString()} / {Number(row.progress_ordered_qty || 0).toLocaleString()}</td>
                <td>{php(row.total_amount || 0)}</td>
                <td className="row wrap">
	                  <button type="button" className="secondary" onClick={() => editRow(row)}>Edit</button>
	                  <button type="button" className="secondary" onClick={() => setStatus(row, 'issued')}>Issue</button>
	                  {row.status !== 'cancelled' && row.status !== 'fully_received' && (
	                    <Link className="button-link secondary-link" href={`/receiving?po_id=${row.id}`}>Receive</Link>
	                  )}
	                  <button type="button" className="secondary" onClick={() => setStatus(row, 'cancelled')}>Cancel</button>
                  <button type="button" className="secondary" onClick={() => removeRow(row)}>Delete</button>
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="7" className="muted">No purchase orders yet.</td></tr>}
          </tbody>
        </table>
      </section>
      </div>
    </div>
  );
}