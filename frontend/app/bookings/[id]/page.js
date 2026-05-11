'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { fetchBooking } from '../../../lib/api';

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function BookingDetailPage({ params }) {
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError('');
    fetchBooking(params.id)
      .then((row) => setBooking(row || null))
      .catch((err) => setError(err.message || 'Failed to load booking.'))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <section className="section">
        <h1>Booking</h1>
        <p className="muted">Loading booking...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="section">
        <h1>Booking</h1>
        <p className="error-text">{error}</p>
        <Link className="button-link secondary-link" href="/bookings/calendar">Back to Calendar</Link>
      </section>
    );
  }

  if (!booking) return null;

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>BOOK-{booking.id}</h1>
            <p className="muted">{booking.guest_full_name || booking.guest_name || 'Guest'} · {booking.status || 'confirmed'}</p>
          </div>
          <div className="row wrap">
            <Link className="button-link secondary-link" href="/bookings/calendar">Calendar</Link>
            <Link className="button-link secondary-link" href="/bookings">Booking List</Link>
            <Link className="button-link secondary-link" href={booking.primary_folio_id ? `/room-folios/${booking.primary_folio_id}` : `/room-folios?booking_id=${booking.id}`}>Open Folio</Link>
          </div>
        </div>
      </section>

      <div className="grid two">
        <section className="section">
          <h2>Stay</h2>
          <table className="table dense-table">
            <tbody>
              <tr><th>Dates</th><td>{booking.check_in || '-'} to {booking.check_out || '-'}</td></tr>
              <tr><th>Room</th><td>{booking.room_display_name || booking.room_name || '-'} · {booking.room_type_display_name || booking.room_type || '-'}</td></tr>
              <tr><th>Rate Plan</th><td>{booking.rate_plan_name || '-'}</td></tr>
              <tr><th>Channel</th><td>{booking.channel_display_name || booking.channel || '-'}</td></tr>
              <tr><th>External</th><td>{booking.external_source ? `${booking.external_source} ${booking.external_booking_id || ''}` : '-'}</td></tr>
            </tbody>
          </table>
        </section>

        <section className="section">
          <h2>Guest & Amounts</h2>
          <table className="table dense-table">
            <tbody>
              <tr><th>Guest</th><td>{booking.guest_full_name || booking.guest_name || '-'}</td></tr>
              <tr><th>Phone</th><td>{booking.guest_phone || '-'}</td></tr>
              <tr><th>Email</th><td>{booking.guest_email || '-'}</td></tr>
              <tr><th>Gross</th><td>{money(booking.gross_amount)}</td></tr>
              <tr><th>Deposit</th><td>{money(booking.deposit_amount)}</td></tr>
            </tbody>
          </table>
        </section>
      </div>

      {booking.notes && (
        <section className="section">
          <h2>Notes</h2>
          <p>{booking.notes}</p>
        </section>
      )}
    </div>
  );
}
