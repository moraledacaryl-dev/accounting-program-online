'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  createRoomFolioLine,
  deleteRoomFolioLine,
  fetchRoomFolio,
  fetchRoomFolios,
  updateRoomFolio,
  updateRoomFolioLine,
  updateRoomFolioStatus,
} from '../../../lib/api';

const LINE_TYPES = [
  'room_charge',
  'package_charge',
  'extra_person',
  'extra_bed',
  'breakfast_addon',
  'manual_charge',
  'deposit',
  'payment',
  'refund',
  'reversal',
];

const EMPTY_LINE = {
  line_type: 'manual_charge',
  description: '',
  quantity: '1',
  unit_price: '0',
  amount: '',
  transaction_date: '',
  reference_no: '',
  notes: '',
};

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function RoomFolioDetailPage({ params }) {
  const folioId = Number(params.id);
  const [folio, setFolio] = useState(null);
  const [editingLineId, setEditingLineId] = useState(null);
  const [lineForm, setLineForm] = useState({ ...EMPTY_LINE, transaction_date: todayIso() });
  const [notesForm, setNotesForm] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const row = await fetchRoomFolio(folioId);
    setFolio(row || null);
    setNotesForm(row?.notes || '');
  }

  useEffect(() => {
    if (!folioId) return;
    load().catch((e) => setError(e.message || 'Failed to load folio.'));
  }, [folioId]);

  const sortedLines = useMemo(() => {
    return [...(folio?.lines || [])].sort((a, b) => {
      const aKey = `${a.transaction_date || ''}-${a.id || 0}`;
      const bKey = `${b.transaction_date || ''}-${b.id || 0}`;
      if (aKey < bKey) return -1;
      if (aKey > bKey) return 1;
      return 0;
    });
  }, [folio]);

  async function submitLine(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        line_type: lineForm.line_type,
        description: lineForm.description || 'Folio line',
        quantity: Number(lineForm.quantity || 0),
        unit_price: Number(lineForm.unit_price || 0),
        amount: lineForm.amount === '' ? null : Number(lineForm.amount || 0),
        transaction_date: lineForm.transaction_date || todayIso(),
        reference_no: lineForm.reference_no || null,
        notes: lineForm.notes || null,
      };
      if (payload.quantity <= 0) {
        setError('Quantity must be greater than zero.');
        return;
      }

      if (editingLineId) {
        await updateRoomFolioLine(editingLineId, payload);
        setNotice('Folio line updated.');
      } else {
        await createRoomFolioLine(folioId, payload);
        setNotice('Folio line added.');
      }
      setEditingLineId(null);
      setLineForm({ ...EMPTY_LINE, transaction_date: todayIso() });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save folio line.');
    }
  }

  function editLine(row) {
    setEditingLineId(row.id);
    setLineForm({
      line_type: row.line_type || 'manual_charge',
      description: row.description || '',
      quantity: String(row.quantity ?? '1'),
      unit_price: String(row.unit_price ?? '0'),
      amount: row.amount == null ? '' : String(row.amount),
      transaction_date: row.transaction_date || todayIso(),
      reference_no: row.reference_no || '',
      notes: row.notes || '',
    });
  }

  async function removeLine(row) {
    if (!window.confirm(`Delete folio line ${row.description}?`)) return;
    setError('');
    try {
      await deleteRoomFolioLine(row.id);
      setNotice('Folio line removed.');
      if (editingLineId === row.id) {
        setEditingLineId(null);
        setLineForm({ ...EMPTY_LINE, transaction_date: todayIso() });
      }
      await load();
    } catch (err) {
      setError(err.message || 'Failed to delete folio line.');
    }
  }

  async function saveFolioMeta() {
    setError('');
    try {
      await updateRoomFolio(folioId, { notes: notesForm || null });
      setNotice('Folio notes updated.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update folio notes.');
    }
  }

  async function setStatus(status) {
    setError('');
    try {
      await updateRoomFolioStatus(folioId, {
        status,
        notes: `Status changed to ${status}`,
      });
      setNotice(`Folio set to ${status}.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update folio status.');
    }
  }

  async function syncOpenSnapshot() {
    setError('');
    try {
      const rows = await fetchRoomFolios({ booking_id: folio?.booking_id, guest_id: folio?.guest_id });
      const open = (rows || []).filter((row) => row.status === 'open').length;
      setNotice(`Loaded ${rows.length} folios for this booking/guest (${open} open).`);
    } catch (err) {
      setError(err.message || 'Failed to fetch related folio snapshot.');
    }
  }

  if (error && !folio) {
    return (
      <section className="section">
        <h1>Room Folio</h1>
        <p className="error-text">{error}</p>
        <Link className="button-link secondary-link" href="/room-folios">Back to Folios</Link>
      </section>
    );
  }

  if (!folio) {
    return (
      <section className="section">
        <h1>Room Folio</h1>
        <p className="muted">Loading folio…</p>
      </section>
    );
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>{folio.folio_no}</h1>
            <p className="muted">Booking {folio.booking_ref || `BOOK-${folio.booking_id}`} · Guest {folio.guest_name || '-'}</p>
          </div>
          <div className="row wrap">
            <span className="badge">{folio.status}</span>
            <Link className="button-link secondary-link" href="/room-folios">Back</Link>
          </div>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="card-grid">
        <section className="card stat-card"><div className="small muted">Charges</div><div className="kpi">{php(folio.charges || 0)}</div></section>
        <section className="card stat-card"><div className="small muted">Payments</div><div className="kpi">{php(folio.payments || 0)}</div></section>
        <section className="card stat-card"><div className="small muted">Deposits</div><div className="kpi">{php(folio.deposits || 0)}</div></section>
        <section className="card stat-card"><div className="small muted">Balance</div><div className="kpi">{php(folio.balance || 0)}</div></section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>{editingLineId ? `Edit Line #${editingLineId}` : 'Add Folio Line'}</h2>
          <form onSubmit={submitLine} className="stack">
            <div className="form-grid">
              <label>Type
                <select value={lineForm.line_type} onChange={(e) => setLineForm((f) => ({ ...f, line_type: e.target.value }))}>
                  {LINE_TYPES.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
              <label>Description<input required value={lineForm.description} onChange={(e) => setLineForm((f) => ({ ...f, description: e.target.value }))} /></label>
              <label>Date<input type="date" value={lineForm.transaction_date} onChange={(e) => setLineForm((f) => ({ ...f, transaction_date: e.target.value }))} /></label>
              <label>Quantity<input type="number" min="0" step="0.01" value={lineForm.quantity} onChange={(e) => setLineForm((f) => ({ ...f, quantity: e.target.value }))} /></label>
              <label>Unit Price<input type="number" min="0" step="0.01" value={lineForm.unit_price} onChange={(e) => setLineForm((f) => ({ ...f, unit_price: e.target.value }))} /></label>
              <label>Amount (optional override)<input type="number" step="0.01" value={lineForm.amount} onChange={(e) => setLineForm((f) => ({ ...f, amount: e.target.value }))} /></label>
              <label>Reference<input value={lineForm.reference_no} onChange={(e) => setLineForm((f) => ({ ...f, reference_no: e.target.value }))} /></label>
            </div>
            <label>Notes<textarea value={lineForm.notes} onChange={(e) => setLineForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">{editingLineId ? 'Update Line' : 'Add Line'}</button>
              {editingLineId && (
                <button type="button" className="secondary" onClick={() => {
                  setEditingLineId(null);
                  setLineForm({ ...EMPTY_LINE, transaction_date: todayIso() });
                }}>
                  Cancel Edit
                </button>
              )}
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Folio Controls</h2>
          <div className="stack">
            <label>Folio Notes
              <textarea value={notesForm} onChange={(e) => setNotesForm(e.target.value)} />
            </label>
            <div className="row wrap">
              <button type="button" className="secondary" onClick={saveFolioMeta}>Save Notes</button>
              <button type="button" className="secondary" onClick={() => setStatus('reviewed')}>Set Reviewed</button>
              <button type="button" className="secondary" onClick={() => setStatus('closed')}>Close Folio</button>
              <button type="button" className="secondary" onClick={() => setStatus('open')}>Reopen</button>
              <button type="button" className="secondary" onClick={syncOpenSnapshot}>Check Related</button>
            </div>
            <p className="small muted">Use `room_charge` and `manual_charge` for charges, `deposit/payment` for collections, and `refund/reversal` for negative payment effects.</p>
          </div>
        </section>
      </div>

      <section className="section">
        <h2>Folio Lines</h2>
        <table className="table">
          <thead><tr><th>Date</th><th>Type</th><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th><th>Reference</th><th></th></tr></thead>
          <tbody>
            {sortedLines.map((row) => (
              <tr key={row.id}>
                <td>{row.transaction_date || '-'}</td>
                <td>{row.line_type}</td>
                <td>{row.description}<br /><span className="small muted">{row.notes || ''}</span></td>
                <td>{Number(row.quantity || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td>{Number(row.unit_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                <td>{php(row.amount || 0)}</td>
                <td>{row.reference_no || '-'}</td>
                <td className="row wrap">
                  <button type="button" className="secondary" onClick={() => editLine(row)}>Edit</button>
                  <button type="button" className="secondary" onClick={() => removeLine(row)}>Delete</button>
                </td>
              </tr>
            ))}
            {!sortedLines.length && <tr><td colSpan="8" className="muted">No folio lines yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
