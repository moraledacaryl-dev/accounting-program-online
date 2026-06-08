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
import ConfirmActionModal from '../../../components/ConfirmActionModal';
import { useConfirmAction } from '../../../components/ConfirmActionProvider';

const LINE_TYPES = [
  'room_charge',
  'package_charge',
  'extra_person',
  'extra_bed',
  'breakfast_addon',
  'minibar',
  'cafe_room_charge',
  'manual_charge',
  'deposit',
  'payment',
  'refund',
  'reversal',
];

const LINE_LABELS = {
  room_charge: 'Room charge',
  package_charge: 'Package charge',
  extra_person: 'Extra guest',
  extra_bed: 'Extra bed',
  breakfast_addon: 'Breakfast',
  minibar: 'Mini bar',
  cafe_room_charge: 'Cafe / room service',
  manual_charge: 'Manual charge',
  deposit: 'Deposit',
  payment: 'Payment',
  refund: 'Refund',
  reversal: 'Reversal',
};

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
  const confirmAction = useConfirmAction();
  const folioId = Number(params.id);
  const [folio, setFolio] = useState(null);
  const [editingLineId, setEditingLineId] = useState(null);
  const [lineForm, setLineForm] = useState({ ...EMPTY_LINE, transaction_date: todayIso() });
  const [notesForm, setNotesForm] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pendingStatus, setPendingStatus] = useState('');

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
  const lineBreakdown = useMemo(() => {
    const totals = new Map();
    for (const row of folio?.lines || []) {
      const key = row.line_type || 'manual_charge';
      totals.set(key, Number(totals.get(key) || 0) + Number(row.amount || 0));
    }
    return [...totals.entries()]
      .map(([lineType, amount]) => ({ lineType, amount }))
      .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount));
  }, [folio]);
  const otherPayments = Number(folio?.payments || 0) - Number(folio?.deposits || 0);

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
    if (!await confirmAction({ title: `Delete folio line ${row.description}?`, description: 'Remove only incorrect draft lines. Settled charges should be handled with a reversal.' })) return;
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

  async function setStatus(status, reason = '') {
    setError('');
    try {
      await updateRoomFolioStatus(folioId, {
        status,
        notes: reason || `Status changed to ${status}`,
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
        <section className="card stat-card"><div className="small muted">Deposits</div><div className="kpi">{php(folio.deposits || 0)}</div></section>
        <section className="card stat-card"><div className="small muted">Other Payments</div><div className="kpi">{php(otherPayments)}</div></section>
        <section className="card stat-card"><div className="small muted">Balance</div><div className="kpi">{php(folio.balance || 0)}</div></section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>{editingLineId ? `Edit Line #${editingLineId}` : 'Add Folio Line'}</h2>
          <form onSubmit={submitLine} className="stack">
            <div className="form-grid">
              <label>Type
                <select value={lineForm.line_type} onChange={(e) => setLineForm((f) => ({ ...f, line_type: e.target.value }))}>
                  {LINE_TYPES.map((value) => <option key={value} value={value}>{LINE_LABELS[value] || value}</option>)}
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
              <button type="button" className="secondary" onClick={() => setPendingStatus('closed')}>Close Folio</button>
              <button type="button" className="secondary" onClick={() => setPendingStatus('open')}>Reopen</button>
              <button type="button" className="secondary" onClick={syncOpenSnapshot}>Check Related</button>
            </div>
            <p className="small muted">Deposits are shown separately here and still reduce the balance; cafe room service should be posted as a charge, not as a payment.</p>
          </div>
        </section>
      </div>

      {!!lineBreakdown.length && (
        <section className="section">
          <h2>Folio Breakdown</h2>
          <table className="table dense-table">
            <thead><tr><th>Bucket</th><th>Amount</th></tr></thead>
            <tbody>
              {lineBreakdown.map((row) => (
                <tr key={row.lineType}>
                  <td>{LINE_LABELS[row.lineType] || row.lineType}</td>
                  <td>{php(row.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="section">
        <h2>Folio Lines</h2>
        <table className="table">
          <thead><tr><th>Date</th><th>Type</th><th>Description</th><th>Qty</th><th>Unit</th><th>Amount</th><th>Reference</th><th></th></tr></thead>
          <tbody>
            {sortedLines.map((row) => (
              <tr key={row.id}>
                <td>{row.transaction_date || '-'}</td>
                <td>{LINE_LABELS[row.line_type] || row.line_type}</td>
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
      <ConfirmActionModal
        open={!!pendingStatus}
        title={pendingStatus === 'closed' ? 'Close this folio?' : 'Reopen this folio?'}
        description={pendingStatus === 'closed' ? 'Confirm the guest folio is ready to close. Further corrections will require reopening it.' : 'Reopening changes the guest billing workflow. Record why a correction is needed.'}
        confirmLabel={pendingStatus === 'closed' ? 'Close folio' : 'Reopen folio'}
        reasonRequired={pendingStatus === 'open'}
        tone={pendingStatus === 'open' ? 'danger' : 'normal'}
        onClose={() => setPendingStatus('')}
        onConfirm={(reason) => setStatus(pendingStatus, reason)}
      />
    </div>
  );
}
