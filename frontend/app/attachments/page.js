'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { API_BASE, deleteAttachment, fetchAttachments, uploadAttachment } from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';
import { useCurrentUser } from '../../lib/useCurrentUser';

const ENTITY_TYPES = [
  'record',
  'stock_movement',
  'sale_order',
  'booking',
  'asset',
  'payroll_run',
  'channel_payout',
  'money_transaction',
  'account_transfer',
  'cash_reconciliation',
  'receivable',
  'payable',
];

function currencyBytes(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function uploadUrl(filePath) {
  const base = API_BASE.replace(/\/api\/?$/, '');
  return `${base}${filePath}`;
}

export default function AttachmentsPage() {
  const { can } = useCurrentUser();
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({
    entity_type: '',
    entity_id: '',
  });
  const [form, setForm] = useState({
    entity_type: 'stock_movement',
    entity_id: '',
    note: '',
  });
  const [file, setFile] = useState(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const filteredRows = useMemo(() => {
    let data = rows;
    if (filters.entity_type) {
      data = data.filter((row) => row.entity_type === filters.entity_type);
    }
    if (filters.entity_id) {
      data = data.filter((row) => Number(row.entity_id) === Number(filters.entity_id));
    }
    return data;
  }, [rows, filters]);

  const canManageAttachments = (
    can('bookings.edit')
    || can('suppliers.manage')
    || can('purchase_requests.create')
    || can('purchase_orders.create')
    || can('receiving.post')
    || can('cashflow.money_in')
    || can('cashflow.money_out')
    || can('cashflow.reconcile')
    || can('payroll_periods.manage')
    || can('assets.manage')
    || can('bir.manage')
  );

  function isSubmittable() {
    return !!file && !!form.entity_type && Number(form.entity_id || 0) > 0;
  }

  async function load() {
    const data = await fetchAttachments({ limit: 300 });
    setRows(Array.isArray(data) ? data : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load attachments.'));
  }, []);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      if (!file) {
        setError('Select a file first.');
        return;
      }
      if (!form.entity_type || !form.entity_id) {
        setError('Entity type and entity id are required.');
        return;
      }
      await uploadAttachment({
        file,
        entityType: form.entity_type,
        entityId: Number(form.entity_id),
        note: form.note || '',
      });
      setNotice('Attachment uploaded.');
      setForm((prev) => ({ ...prev, note: '' }));
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await load();
    } catch (e2) {
      setError(e2.message || 'Failed to upload attachment.');
    }
  }

  async function removeAttachment(id) {
    setError('');
    setNotice('');
    try {
      await deleteAttachment(id);
      setNotice('Attachment deleted.');
      await load();
    } catch (e) {
      setError(e.message || 'Failed to delete attachment.');
    }
  }

  return (
    <div>
      <section className="section">
        <h1>Attachments</h1>
        <p className="muted">Attach receipts and supporting documents to records and operational transactions.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>Upload Attachment</h2>
          <form onSubmit={submit} onKeyDown={(event) => shouldPreventEnterSubmit(event, isSubmittable)}>
            <div className="form-grid">
              <label>
                Entity Type
                <select value={form.entity_type} onChange={(e) => setForm((f) => ({ ...f, entity_type: e.target.value }))}>
                  {ENTITY_TYPES.map((row) => (
                    <option key={row} value={row}>{row}</option>
                  ))}
                </select>
              </label>
              <label>
                Entity ID
                <input type="number" min="1" value={form.entity_id} onChange={(e) => setForm((f) => ({ ...f, entity_id: e.target.value }))} />
              </label>
              <label>
                File
                <input ref={fileInputRef} type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              </label>
            </div>
            <label>
              Note
              <textarea value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
            </label>
            <button type="submit" disabled={!canManageAttachments || !isSubmittable()}>Upload</button>
            {!canManageAttachments && <p className="small muted">You can view files but cannot upload/delete with your current role.</p>}
          </form>
        </section>

        <section className="section">
          <h2>Filters</h2>
          <div className="form-grid">
            <label>
              Entity Type
              <select value={filters.entity_type} onChange={(e) => setFilters((f) => ({ ...f, entity_type: e.target.value }))}>
                <option value="">All</option>
                {ENTITY_TYPES.map((row) => (
                  <option key={row} value={row}>{row}</option>
                ))}
              </select>
            </label>
            <label>
              Entity ID
              <input type="number" min="1" value={filters.entity_id} onChange={(e) => setFilters((f) => ({ ...f, entity_id: e.target.value }))} />
            </label>
          </div>
        </section>
      </div>

      <section className="section">
        <h2>Files</h2>
        <table className="table">
          <thead><tr><th>Entity</th><th>Filename</th><th>Size</th><th>Note</th><th>Uploaded</th><th></th></tr></thead>
          <tbody>
            {filteredRows.map((row) => (
              <tr key={row.id}>
                <td>{row.entity_type} · {row.entity_id}</td>
                <td><a href={uploadUrl(row.file_path)} target="_blank" rel="noreferrer">{row.file_name}</a></td>
                <td>{currencyBytes(row.size_bytes)}</td>
                <td>{row.note || '-'}</td>
                <td>{row.created_at || '-'}</td>
                <td>
                  {canManageAttachments ? (
                    <button className="secondary" onClick={() => removeAttachment(row.id)}>Delete</button>
                  ) : (
                    <span className="small muted">View only</span>
                  )}
                </td>
              </tr>
            ))}
            {!filteredRows.length && <tr><td colSpan="6" className="muted">No attachments found.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
