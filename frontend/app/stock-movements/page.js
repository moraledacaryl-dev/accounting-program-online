'use client';
import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';
import { useEffect, useMemo, useState } from 'react';
import {
  createStockMovement,
  deleteAttachment,
  downloadAttachment,
  fetchAllocations,
  fetchAttachments,
  fetchBatches,
  fetchInventoryItems,
  fetchStockMovements,
  uploadAttachment,
} from '../../lib/api';
import { useConfirmAction } from '../../components/ConfirmActionProvider';

const REASON_OPTIONS = [
  'Purchase',
  'Restock',
  'Adjustment In',
  'Adjustment Out',
  'Transfer In',
  'Transfer Out',
  'Return In',
  'Return Out',
  'Spoilage',
  'Wastage',
  'Staff Use',
  'Recipe Production',
  'Complimentary',
  'Correction',
];
const MOVEMENT_TYPES = [
  { value: 'in', label: 'Stock in' },
  { value: 'out', label: 'Stock out' },
];
const MODULE_OPTIONS = ['inventory', 'procurement', 'restaurant', 'breakfast', 'cafe', 'bar', 'rooms', 'finance', 'admin'];
const EXPENSE_MODULES = ['procurement', 'inventory', 'finance', 'restaurant', 'cafe'];
const PAYMENT_METHODS = ['cash', 'card', 'gcash', 'bank_transfer', 'credit'];

export default function StockMovementsPage() {
  const confirmAction = useConfirmAction();
  const [items, setItems] = useState([]);
  const [movements, setMovements] = useState([]);
  const [batches, setBatches] = useState([]);
  const [alloc, setAlloc] = useState([]);
  const [selectedMovement, setSelectedMovement] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [receiptFile, setReceiptFile] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [form, setForm] = useState({
    item_id: '',
    movement_type: 'in',
    quantity: '',
    total_item_cost: '',
    delivery_cost: '',
    other_cost: '',
    reason: 'Purchase',
    module_slug: 'inventory',
    reference_no: '',
    movement_date: '',
    supplier: '',
    notes: '',
    log_expense: false,
    expense_module_slug: 'procurement',
    expense_payment_method: 'cash',
    expense_counterparty: '',
    expense_notes: '',
  });

  async function load() {
    setError('');
    try {
      setItems(await fetchInventoryItems());
      setMovements(await fetchStockMovements());
      setBatches(await fetchBatches());
      setAttachments(await fetchAttachments({ entityType: 'stock_movement', limit: 200 }));
    } catch (err) {
      setError(err.message || 'Unable to load stock movement data.');
    }
  }

  useEffect(() => { load().catch(console.error); }, []);

  const inventoryById = useMemo(() => Object.fromEntries(items.map((item) => [item.id, item])), [items]);
  const batchMap = useMemo(() => Object.fromEntries(batches.map((batch) => [batch.id, batch])), [batches]);

  const totalItemCost = Number(form.total_item_cost || 0);
  const deliveryCost = Number(form.delivery_cost || 0);
  const otherCost = Number(form.other_cost || 0);
  const landedTotal = totalItemCost + deliveryCost + otherCost;
  const derivedUnitCost = Number(form.quantity || 0) > 0 ? landedTotal / Number(form.quantity || 0) : 0;

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    if (!form.item_id) {
      setError('Choose an inventory item.');
      return;
    }
    if (Number(form.quantity || 0) <= 0) {
      setError('Quantity must be greater than zero.');
      return;
    }
    try {
      const payload = {
        ...form,
        item_id: Number(form.item_id),
        quantity: Number(form.quantity || 0),
        unit_cost: form.movement_type === 'in' ? derivedUnitCost : 0,
        total_item_cost: form.movement_type === 'in' ? totalItemCost : undefined,
        delivery_cost: form.movement_type === 'in' ? deliveryCost : undefined,
        other_cost: form.movement_type === 'in' ? otherCost : undefined,
        log_expense: !!form.log_expense,
        expense_module_slug: form.expense_module_slug || (form.movement_type === 'out' ? 'inventory' : 'procurement'),
      };
      const movement = await createStockMovement(payload);
      if (receiptFile && movement?.id) {
        await uploadAttachment({
          file: receiptFile,
          entityType: 'stock_movement',
          entityId: movement.id,
          note: form.notes || form.expense_notes || (form.reference_no ? `Receipt for ${form.reference_no}` : 'Supplier receipt'),
        });
      }
      setForm({
        item_id: '',
        movement_type: 'in',
        quantity: '',
        total_item_cost: '',
        delivery_cost: '',
        other_cost: '',
        reason: 'Purchase',
        module_slug: 'inventory',
        reference_no: '',
        movement_date: '',
        supplier: '',
        notes: '',
        log_expense: false,
        expense_module_slug: 'procurement',
        expense_payment_method: 'cash',
        expense_counterparty: '',
        expense_notes: '',
      });
      setReceiptFile(null);
      setNotice(receiptFile ? 'Stock movement and receipt attachment saved.' : 'Stock movement saved.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save stock movement.');
    }
  }

  const attachmentCountByMovement = attachments.reduce((map, row) => {
    const key = Number(row.entity_id || 0);
    map[key] = (map[key] || 0) + 1;
    return map;
  }, {});

  async function removeAttachment(id) {
    if (!await confirmAction({ title: `Delete attachment #${id}?`, description: 'The supporting document will no longer be available from this stock movement.' })) return;
    setError('');
    setNotice('');
    try {
      await deleteAttachment(id);
      setNotice('Attachment deleted.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete attachment.');
    }
  }

  async function openAttachment(row) {
    setError('');
    const openedWindow = window.open('', '_blank');
    if (!openedWindow) {
      setError('Browser blocked the attachment window. Allow pop-ups for this site and try again.');
      return;
    }
    openedWindow.opener = null;
    try {
      const { blob } = await downloadAttachment(row.id);
      const url = URL.createObjectURL(blob);
      openedWindow.location.href = url;
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      openedWindow.close();
      setError(err.message || 'Failed to open attachment.');
    }
  }

  async function showAllocations(movementId) {
    setSelectedMovement(movementId);
    setAlloc(await fetchAllocations(movementId));
  }

  return (
    <div>
      <LegacyExternalModuleNotice appName="Inventory & Procurement" />
      <div>
      <section className="section">
        <h1>Stock Movements</h1>
        <p className="muted">Record stock in and out by item. For purchases, enter landed cost and the system calculates unit cost for you.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>Inventory item<select required value={form.item_id} onChange={e => setForm((f) => ({ ...f, item_id: e.target.value }))}>
                <option value="">Select item</option>
                {items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select></label>
              <label>Movement type<select value={form.movement_type} onChange={e => setForm((f) => ({ ...f, movement_type: e.target.value, expense_module_slug: e.target.value === 'out' ? 'inventory' : 'procurement' }))}>
                {MOVEMENT_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
              </select></label>
              <label>Quantity<input required type="number" step="0.01" min="0.01" inputMode="decimal" value={form.quantity} onChange={e => setForm((f) => ({ ...f, quantity: e.target.value }))} /></label>
              <label>Reason<select value={form.reason} onChange={e => setForm((f) => ({ ...f, reason: e.target.value }))}>
                {REASON_OPTIONS.map((reason) => <option key={reason} value={reason}>{reason}</option>)}
              </select></label>
              <label>Source area<select value={form.module_slug} onChange={e => setForm((f) => ({ ...f, module_slug: e.target.value }))}>
                {MODULE_OPTIONS.map((module) => <option key={module} value={module}>{module.charAt(0).toUpperCase() + module.slice(1)}</option>)}
              </select></label>
              <label>Reference<input value={form.reference_no} onChange={e => setForm((f) => ({ ...f, reference_no: e.target.value }))} placeholder="Purchase order, memo, etc." /></label>
              <label>Date<input type="date" value={form.movement_date} onChange={e => setForm((f) => ({ ...f, movement_date: e.target.value }))} /></label>
              <label>Supplier<input value={form.supplier} onChange={e => setForm((f) => ({ ...f, supplier: e.target.value }))} /></label>
            </div>
            <p className="muted small">Stock in is for receiving and landed-cost entry. Stock out is for usage, transfers, and corrections.</p>

            {form.movement_type === 'in' && (
              <section className="section">
                <h3>Purchase cost</h3>
                <div className="form-grid">
                  <label>Total item cost<input type="number" step="0.01" min="0" inputMode="decimal" value={form.total_item_cost} onChange={e => setForm((f) => ({ ...f, total_item_cost: e.target.value }))} /></label>
                  <label>Delivery cost<input type="number" step="0.01" min="0" inputMode="decimal" value={form.delivery_cost} onChange={e => setForm((f) => ({ ...f, delivery_cost: e.target.value }))} /></label>
                  <label>Other landed cost<input type="number" step="0.01" min="0" inputMode="decimal" value={form.other_cost} onChange={e => setForm((f) => ({ ...f, other_cost: e.target.value }))} /></label>
                  <label>Landed total<input type="text" readOnly value={`₱${landedTotal.toFixed(2)}`} /></label>
                  <label>Derived unit cost<input type="text" readOnly value={`₱${derivedUnitCost.toFixed(2)}`} /></label>
                </div>
              </section>
            )}

            <section className="section">
              <h3>Accounting options</h3>
              <div className="form-grid">
                <label className="checkbox-row">
                  <input type="checkbox" checked={form.log_expense} onChange={e => setForm((f) => ({ ...f, log_expense: e.target.checked }))} />
                  Record expense
                </label>
              </div>
              {form.log_expense && (
                <div className="form-grid" style={{ marginTop: 12 }}>
                  <label>Expense module<select value={form.expense_module_slug} onChange={e => setForm((f) => ({ ...f, expense_module_slug: e.target.value }))}>
                    {EXPENSE_MODULES.map((module) => <option key={module} value={module}>{module.charAt(0).toUpperCase() + module.slice(1)}</option>)}
                  </select></label>
                  <label>Payment method<select value={form.expense_payment_method} onChange={e => setForm((f) => ({ ...f, expense_payment_method: e.target.value }))}>
                    {PAYMENT_METHODS.map((method) => <option key={method} value={method}>{method === 'gcash' ? 'GCash' : method.charAt(0).toUpperCase() + method.slice(1)}</option>)}
                  </select></label>
                  <label>Counterparty<input value={form.expense_counterparty} onChange={e => setForm((f) => ({ ...f, expense_counterparty: e.target.value }))} /></label>
                  <label>Expense notes<textarea value={form.expense_notes} onChange={e => setForm((f) => ({ ...f, expense_notes: e.target.value }))} /></label>
                </div>
              )}
            </section>
            <label>Notes<textarea value={form.notes} onChange={e => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <label>Receipt<input type="file" onChange={e => setReceiptFile(e.target.files?.[0] || null)} /></label>
            <button type="submit">Save movement</button>
          </form>
        </section>

        <section className="section">
          <h2>Open Batches</h2>
          <table className="table">
            <thead><tr><th>Item</th><th>Batch</th><th>Remaining</th><th>Unit cost</th></tr></thead>
            <tbody>
              {batches.filter((b) => !b.is_closed).map((b) => (
                <tr key={b.id}>
                  <td>{inventoryById[b.item_id]?.name || `#${b.item_id}`}</td>
                  <td>{b.batch_code || `#${b.id}`}</td>
                  <td>{b.quantity_remaining}</td>
                  <td>{Number(b.unit_cost || 0).toFixed(2)}</td>
                </tr>
              ))}
              {!batches.filter((b) => !b.is_closed).length && (
                <tr><td colSpan="4" className="muted">No open batches at the moment.</td></tr>
              )}
            </tbody>
          </table>
        </section>
      </div>

      <section className="section">
        <h2>Movements</h2>
        <table className="table">
          <thead><tr><th>Movement</th><th>Item</th><th>Type</th><th>Qty</th><th>Landed total</th><th>Reason</th><th>Attachments</th><th></th></tr></thead>
          <tbody>
            {movements.map((m) => (
              <tr key={m.id}>
                <td>#{m.id}</td>
                <td>{inventoryById[m.item_id]?.name || `#${m.item_id}`}</td>
                <td>{m.movement_type === 'in' ? 'Stock in' : 'Stock out'}</td>
                <td>{m.quantity}</td>
                <td>{Number(m.total_cost || 0).toLocaleString()}</td>
                <td>{m.reason || '-'}</td>
                <td>{attachmentCountByMovement[Number(m.id)] || 0}</td>
                <td><button className="secondary" onClick={() => showAllocations(m.id)}>Allocations</button></td>
              </tr>
            ))}
            {!movements.length && (
              <tr><td colSpan="8" className="muted">No stock movements recorded yet.</td></tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Receipt Attachments</h2>
        <table className="table dense-table">
          <thead><tr><th>Movement</th><th>File</th><th>Size</th><th>Note</th><th></th></tr></thead>
          <tbody>
            {attachments.map((a) => (
              <tr key={a.id}>
                <td>Movement #{a.entity_id}</td>
                <td><button type="button" className="button-link secondary-link" onClick={() => openAttachment(a)}>{a.file_name}</button></td>
                <td>{(Number(a.size_bytes || 0) / 1024).toFixed(1)} KB</td>
                <td>{a.note || '-'}</td>
                <td><button className="secondary" onClick={async () => { await removeAttachment(a.id); }}>Delete</button></td>
              </tr>
            ))}
            {!attachments.length && <tr><td colSpan="5" className="muted">No attachments yet.</td></tr>}
          </tbody>
        </table>
      </section>

      {selectedMovement && (
        <section className="section">
          <h2>Allocations for Movement #{selectedMovement}</h2>
          <table className="table">
            <thead><tr><th>Batch</th><th>Qty</th><th>Unit Cost</th><th>Total</th></tr></thead>
            <tbody>
              {alloc.map((a) => (
                <tr key={a.id}>
                  <td>{batchMap[a.batch_id]?.batch_code || `#${a.batch_id}`}</td>
                  <td>{a.quantity}</td>
                  <td>{Number(a.unit_cost || 0).toFixed(2)}</td>
                  <td>{Number(a.total_cost || 0).toFixed(2)}</td>
                </tr>
              ))}
              {!alloc.length && <tr><td colSpan="4" className="muted">No allocations available for this movement.</td></tr>}
            </tbody>
          </table>
        </section>
      )}
      </div>
    </div>
  );
}