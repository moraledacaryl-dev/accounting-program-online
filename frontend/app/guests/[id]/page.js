'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { fetchGuestHistory, fetchRoomFolios } from '../../../lib/api';

function php(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function compactDate(value) {
  if (!value) return '-';
  return String(value).slice(0, 10);
}

export default function GuestProfilePage({ params }) {
  const guestId = Number(params.id);
  const [history, setHistory] = useState(null);
  const [guestFolios, setGuestFolios] = useState([]);
  const [error, setError] = useState('');

  async function load() {
    const [guestHistory, folios] = await Promise.all([
      fetchGuestHistory(guestId),
      fetchRoomFolios({ guest_id: guestId }),
    ]);
    setHistory(guestHistory || null);
    setGuestFolios(Array.isArray(folios) ? folios : []);
  }

  useEffect(() => {
    if (!guestId) return;
    load().catch((e) => setError(e.message || 'Failed to load guest profile.'));
  }, [guestId]);

  const guest = history?.guest || null;
  const bookings = history?.bookings || [];
  const stayHistory = history?.stay_history || [];
  const paymentHistory = history?.payment_history || [];
  const folioHistory = history?.folio_history || [];

  const stats = useMemo(() => {
    const bookingCount = Number(guest?.booking_count || bookings.length || 0);
    const stayCount = Number(guest?.stay_count || stayHistory.length || 0);
    const outstanding = Number(history?.outstanding_balance || guest?.outstanding_balance || 0);
    const payments = paymentHistory.reduce((acc, row) => {
      const type = String(row.line_type || '').toLowerCase();
      const amount = Number(row.amount || 0);
      if (type === 'refund' || type === 'reversal') return acc - amount;
      return acc + amount;
    }, 0);
    return {
      bookingCount,
      stayCount,
      outstanding,
      payments,
    };
  }, [guest, bookings, stayHistory, paymentHistory, history]);

  if (error) {
    return (
      <section className="section">
        <h1>Guest Profile</h1>
        <p className="error-text">{error}</p>
        <Link className="button-link secondary-link" href="/guests">Back to Guests</Link>
      </section>
    );
  }

  if (!guest) {
    return (
      <section className="section">
        <h1>Guest Profile</h1>
        <p className="muted">Loading guest data…</p>
      </section>
    );
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>{guest.full_name}</h1>
            <p className="muted">Guest profile with booking, stay, payment, and folio history.</p>
          </div>
          <div className="row wrap">
            {guest.vip_flag ? <span className="badge">VIP</span> : null}
            {!guest.is_active ? <span className="badge">Inactive</span> : null}
            <Link className="button-link secondary-link" href="/guests">Back to Guests</Link>
          </div>
        </div>
      </section>

      <div className="card-grid">
        <section className="card stat-card">
          <div className="small muted">Bookings</div>
          <div className="kpi">{stats.bookingCount}</div>
        </section>
        <section className="card stat-card">
          <div className="small muted">Stays</div>
          <div className="kpi">{stats.stayCount}</div>
        </section>
        <section className="card stat-card">
          <div className="small muted">Payments Total</div>
          <div className="kpi">{php(stats.payments)}</div>
        </section>
        <section className="card stat-card">
          <div className="small muted">Outstanding Balance</div>
          <div className="kpi">{php(stats.outstanding)}</div>
        </section>
      </div>

      <div className="grid">
        <section className="section">
          <h2>Identity & Preferences</h2>
          <table className="table dense-table">
            <tbody>
              <tr><th>Phone</th><td>{guest.phone || '-'}</td></tr>
              <tr><th>Email</th><td>{guest.email || '-'}</td></tr>
              <tr><th>Address</th><td>{guest.address || '-'}</td></tr>
              <tr><th>City</th><td>{guest.city || '-'}</td></tr>
              <tr><th>Nationality</th><td>{guest.nationality || '-'}</td></tr>
              <tr><th>Birthday</th><td>{guest.birthday || '-'}</td></tr>
              <tr><th>Company</th><td>{guest.company || '-'}</td></tr>
              <tr><th>Status Tags</th><td>{guest.status_tags || '-'}</td></tr>
              <tr><th>Tags</th><td>{(guest.tags || []).join(', ') || '-'}</td></tr>
              <tr>
                <th>Preferences</th>
                <td>
                  {(guest.preferences || []).length
                    ? guest.preferences.map((pref) => `${pref.preference_key}: ${pref.preference_value || ''}`).join(', ')
                    : '-'}
                </td>
              </tr>
              <tr><th>Notes</th><td>{guest.notes || '-'}</td></tr>
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Open Folios</h2>
          <table className="table">
            <thead><tr><th>Folio</th><th>Booking</th><th>Status</th><th>Balance</th><th></th></tr></thead>
            <tbody>
              {guestFolios.map((row) => (
                <tr key={row.id}>
                  <td>{row.folio_no}</td>
                  <td>{row.booking_ref || `BOOK-${row.booking_id}`}</td>
                  <td>{row.status}</td>
                  <td>{php(row.balance || 0)}</td>
                  <td><Link className="button-link secondary-link" href={`/room-folios/${row.id}`}>Open</Link></td>
                </tr>
              ))}
              {!guestFolios.length && <tr><td colSpan="5" className="muted">No folios found for this guest.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <section className="section">
        <h2>Booking History</h2>
        <table className="table">
          <thead><tr><th>Booking</th><th>Status</th><th>Room</th><th>Channel</th><th>Stay</th><th>Amounts</th></tr></thead>
          <tbody>
            {bookings.map((row) => (
              <tr key={row.id}>
                <td>BOOK-{row.id}</td>
                <td>{row.status}</td>
                <td>{row.room_name || '-'}<br /><span className="small muted">{row.room_type || '-'}</span></td>
                <td>{row.channel || '-'}</td>
                <td>{compactDate(row.check_in)} → {compactDate(row.check_out)}</td>
                <td>
                  Gross {php(row.gross_amount || 0)}
                  <br />
                  <span className="small muted">Deposit {php(row.deposit_amount || 0)}</span>
                </td>
              </tr>
            ))}
            {!bookings.length && <tr><td colSpan="6" className="muted">No bookings yet.</td></tr>}
          </tbody>
        </table>
      </section>

      <div className="grid">
        <section className="section">
          <h2>Stay History</h2>
          <table className="table dense-table">
            <thead><tr><th>Booking</th><th>Status</th><th>Room</th><th>Dates</th></tr></thead>
            <tbody>
              {stayHistory.map((row) => (
                <tr key={`stay-${row.booking_id}`}>
                  <td>BOOK-{row.booking_id}</td>
                  <td>{row.status}</td>
                  <td>{row.room_name || '-'} / {row.room_type || '-'}</td>
                  <td>{compactDate(row.check_in)} → {compactDate(row.check_out)}</td>
                </tr>
              ))}
              {!stayHistory.length && <tr><td colSpan="4" className="muted">No completed stays yet.</td></tr>}
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Payment History</h2>
          <table className="table dense-table">
            <thead><tr><th>Date</th><th>Type</th><th>Folio</th><th>Reference</th><th>Amount</th></tr></thead>
            <tbody>
              {paymentHistory.map((row) => (
                <tr key={`pay-${row.id}`}>
                  <td>{compactDate(row.transaction_date)}</td>
                  <td>{row.line_type}</td>
                  <td>{row.folio_no}</td>
                  <td>{row.reference_no || '-'}</td>
                  <td>{php(row.amount || 0)}</td>
                </tr>
              ))}
              {!paymentHistory.length && <tr><td colSpan="5" className="muted">No payment activity yet.</td></tr>}
            </tbody>
          </table>
        </section>
      </div>

      <section className="section">
        <h2>Folio Summary History</h2>
        <table className="table">
          <thead><tr><th>Folio</th><th>Status</th><th>Charges</th><th>Payments</th><th>Balance</th></tr></thead>
          <tbody>
            {folioHistory.map((row) => (
              <tr key={`folio-${row.id}`}>
                <td>{row.folio_no}</td>
                <td>{row.status}</td>
                <td>{php(row.charges || 0)}</td>
                <td>{php(row.payments || 0)}</td>
                <td>{php(row.balance || 0)}</td>
              </tr>
            ))}
            {!folioHistory.length && <tr><td colSpan="5" className="muted">No folio history yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
