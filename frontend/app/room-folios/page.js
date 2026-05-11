'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  createRoomFolio,
  fetchBookings,
  fetchGuests,
  fetchRoomFolios,
  updateRoomFolioStatus,
} from '../../lib/api';

const STATUS_ALL = '__all__';

const EMPTY_FORM = {
  booking_id: '',
  guest_id: '',
  folio_no: '',
  notes: '',
};

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function RoomFoliosPage() {
  const [rows, setRows] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [guests, setGuests] = useState([]);
  const [statusFilter, setStatusFilter] = useState(STATUS_ALL);
  const [bookingFilter, setBookingFilter] = useState('');
  const [guestFilter, setGuestFilter] = useState('');
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const [folioData, bookingData, guestData] = await Promise.all([
      fetchRoomFolios({
        status: statusFilter !== STATUS_ALL ? statusFilter : undefined,
        booking_id: bookingFilter ? Number(bookingFilter) : undefined,
        guest_id: guestFilter ? Number(guestFilter) : undefined,
      }),
      fetchBookings(),
      fetchGuests({ active_only: true, limit: 500 }),
    ]);
    setRows(Array.isArray(folioData) ? folioData : []);
    setBookings(Array.isArray(bookingData) ? bookingData : []);
    setGuests(Array.isArray(guestData) ? guestData : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load folios.'));
  }, [statusFilter, bookingFilter, guestFilter]);

  const bookingById = useMemo(() => {
    const map = new Map();
    for (const row of bookings) map.set(row.id, row);
    return map;
  }, [bookings]);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      if (!form.booking_id) {
        setError('Select a booking to create folio.');
        return;
      }
      const booking = bookingById.get(Number(form.booking_id));
      await createRoomFolio({
        booking_id: Number(form.booking_id),
        guest_id: form.guest_id ? Number(form.guest_id) : (booking?.guest_id || null),
        folio_no: form.folio_no || null,
        notes: form.notes || null,
      });
      setForm({ ...EMPTY_FORM });
      setNotice('Room folio created.');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to create folio.');
    }
  }

  async function setStatus(row, status) {
    setError('');
    try {
      await updateRoomFolioStatus(row.id, {
        status,
        notes: status === 'closed' ? 'Closed from folio list' : null,
      });
      setNotice(`Folio ${row.folio_no} marked as ${status}.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to update folio status.');
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <h1>Room Folios</h1>
            <p className="muted">Room folios are your invoice/ledger history: charges, extras, deposits, payments, refunds, and balances for open and closed stays.</p>
          </div>
          <div className="row wrap">
            <label style={{ minWidth: 160 }}>
              Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value={STATUS_ALL}>All statuses (default)</option>
                <option value="open">open</option>
                <option value="reviewed">reviewed</option>
                <option value="closed">closed</option>
                <option value="cancelled">cancelled</option>
              </select>
            </label>
            <label style={{ minWidth: 180 }}>
              Booking
              <select value={bookingFilter} onChange={(e) => setBookingFilter(e.target.value)}>
                <option value="">All</option>
                {bookings.map((row) => (
                  <option key={row.id} value={row.id}>BOOK-{row.id} · {row.guest_name}</option>
                ))}
              </select>
            </label>
            <label style={{ minWidth: 180 }}>
              Guest
              <select value={guestFilter} onChange={(e) => setGuestFilter(e.target.value)}>
                <option value="">All</option>
                {guests.map((row) => (
                  <option key={row.id} value={row.id}>{row.full_name}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <div className="grid">
        <section className="section">
          <h2>Create Folio</h2>
          <form onSubmit={submit} className="stack">
            <div className="form-grid">
              <label>Booking
                <select value={form.booking_id} onChange={(e) => {
                  const nextBookingId = e.target.value;
                  const booking = bookingById.get(Number(nextBookingId));
                  setForm((f) => ({
                    ...f,
                    booking_id: nextBookingId,
                    guest_id: booking?.guest_id ? String(booking.guest_id) : f.guest_id,
                  }));
                }}>
                  <option value="">Select booking</option>
                  {bookings.map((row) => (
                    <option key={row.id} value={row.id}>BOOK-{row.id} · {row.guest_name} · {row.room_name || row.room_display_name || '-'}</option>
                  ))}
                </select>
              </label>
              <label>Guest (override)
                <select value={form.guest_id} onChange={(e) => setForm((f) => ({ ...f, guest_id: e.target.value }))}>
                  <option value="">Use booking guest</option>
                  {guests.map((row) => (
                    <option key={row.id} value={row.id}>{row.full_name}</option>
                  ))}
                </select>
              </label>
              <label>Folio No (optional)<input value={form.folio_no} onChange={(e) => setForm((f) => ({ ...f, folio_no: e.target.value }))} /></label>
            </div>
            <label>Notes<textarea value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
            <div className="row wrap">
              <button type="submit">Create Folio</button>
              <button type="button" className="secondary" onClick={() => setForm({ ...EMPTY_FORM })}>Clear</button>
            </div>
          </form>
        </section>

        <section className="section">
          <h2>Balances Snapshot</h2>
          <table className="table dense-table">
            <tbody>
              <tr><th>Open folios</th><td>{rows.filter((row) => row.status === 'open').length}</td></tr>
              <tr><th>Reviewed folios</th><td>{rows.filter((row) => row.status === 'reviewed').length}</td></tr>
              <tr><th>Closed folios</th><td>{rows.filter((row) => row.status === 'closed').length}</td></tr>
              <tr>
                <th>Total open balance</th>
                <td>{php(rows.filter((row) => row.status !== 'closed' && row.status !== 'cancelled').reduce((acc, row) => acc + Number(row.balance || 0), 0))}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

        <section className="section">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Folio / Invoice List</h2>
            <p className="muted small">{rows.length} record(s) loaded.</p>
          </div>
          <table className="table">
          <thead><tr><th>Folio</th><th>Booking</th><th>Guest</th><th>Status</th><th>Charges</th><th>Payments</th><th>Balance</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.folio_no}</td>
                <td>{row.booking_ref || `BOOK-${row.booking_id}`}</td>
                <td>{row.guest_name || '-'}</td>
                <td>{row.status}</td>
                <td>{php(row.charges || 0)}</td>
                <td>{php(row.payments || 0)}</td>
                <td>{php(row.balance || 0)}</td>
                <td className="row wrap">
                  <Link className="button-link secondary-link" href={`/room-folios/${row.id}`}>Open</Link>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'reviewed')}>Review</button>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'closed')}>Close</button>
                  <button type="button" className="secondary" onClick={() => setStatus(row, 'open')}>Reopen</button>
                </td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan="8" className="muted">No folios found.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
