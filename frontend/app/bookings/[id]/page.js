'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useConfirmAction } from '../../../components/ConfirmActionProvider';
import { fetchBooking, fetchBreakfastLogs, reclassifyBookingFolioLines } from '../../../lib/api';
import { useCurrentUser } from '../../../lib/useCurrentUser';

function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function signedMoney(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'always' });
}

export default function BookingDetailPage({ params }) {
  const { can } = useCurrentUser();
  const confirmAction = useConfirmAction();
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [classificationRunning, setClassificationRunning] = useState(false);
  const [classificationResult, setClassificationResult] = useState(null);
  const [breakfastLogs, setBreakfastLogs] = useState([]);
  const canRepairFolio = can('folios.manage') || can('bookings.edit');

  useEffect(() => {
    setLoading(true);
    setError('');
    Promise.all([fetchBooking(params.id), fetchBreakfastLogs()])
      .then(([row, logs]) => {
        setBooking(row || null);
        setBreakfastLogs((Array.isArray(logs) ? logs : []).filter((item) => Number(item.booking_id) === Number(params.id)));
      })
      .catch((err) => setError(err.message || 'Failed to load booking.'))
      .finally(() => setLoading(false));
  }, [params.id]);

  async function runClassification(dryRun) {
    if (!canRepairFolio) return;
    if (!dryRun) {
      if (!classificationResult?.dry_run) {
        setError('Preview the suggested corrections before applying them.');
        return;
      }
      const confirmed = await confirmAction({
        title: `Apply ${classificationResult.changed || 0} folio classification corrections?`,
        description: `Amounts stay unchanged. The resulting folio balance adjustment is ${signedMoney(classificationResult.balance_adjustment || 0)}.`,
        confirmLabel: 'Apply Corrections',
      });
      if (!confirmed) return;
    }
    setClassificationRunning(true);
    setError('');
    setNotice('');
    try {
      const result = await reclassifyBookingFolioLines(params.id, {
        dry_run: !!dryRun,
        include_payment_lines: true,
        limit: 1000,
      });
      setClassificationResult(result || null);
      setNotice(result?.dry_run
        ? `Classification preview ready: ${result?.changed || 0} suggested corrections.`
        : `Folio classifications updated: ${result?.changed || 0} corrected.`);
    } catch (err) {
      setError(err.message || 'Failed to review folio classifications.');
    } finally {
      setClassificationRunning(false);
    }
  }

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

      <section className="section">
        <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2>Breakfast Status</h2>
            <p className="muted">Breakfast service is recorded in POS. Accounting displays entitlement, service usage, excess charges, and the linked folio result.</p>
          </div>
          <button type="button" className="secondary">Open in POS</button>
        </div>
        <div className="card-grid" style={{ marginTop: 10 }}>
          <div className="card"><div className="small muted">Included</div><div className="kpi compact-kpi">{booking.breakfast_included_count ?? booking.adults ?? '-'}</div></div>
          <div className="card"><div className="small muted">Served</div><div className="kpi compact-kpi">{breakfastLogs.reduce((sum, item) => sum + Number(item.quantity || item.served_count || 0), 0)}</div></div>
          <div className="card"><div className="small muted">Excess</div><div className="kpi compact-kpi">{breakfastLogs.reduce((sum, item) => sum + Number(item.excess_quantity || 0), 0)}</div></div>
        </div>
      </section>

      <section className="section">
        <h2>Operations Links</h2>
        <p className="muted">Housekeeping readiness and operational execution remain in Operations Command Center.</p>
        <div className="row wrap"><button type="button" className="secondary">Open Housekeeping</button><button type="button" className="secondary">Open Event Links</button></div>
      </section>

      {canRepairFolio && (
        <section className="section">
          <h2>Review Existing Folio Classifications</h2>
          <p className="muted">
            Use this on older bookings when imported rows look like payments but their descriptions indicate room charges, breakfast, minibar, extra guests, extra beds, or room service. Preview first: amounts remain unchanged, but correcting a payment into a charge updates the folio balance.
          </p>
          <div className="row wrap">
            <button type="button" className="secondary" onClick={() => runClassification(true)} disabled={classificationRunning}>
              {classificationRunning ? 'Checking...' : 'Preview Suggested Corrections'}
            </button>
            <button type="button" className="danger" onClick={() => runClassification(false)} disabled={classificationRunning || !classificationResult?.dry_run || !classificationResult?.changed}>
              Apply Suggested Corrections
            </button>
            <Link className="button-link secondary-link" href={booking.primary_folio_id ? `/room-folios/${booking.primary_folio_id}` : `/room-folios?booking_id=${booking.id}`}>Open Folio</Link>
          </div>
          {!!notice && <p className="success-text">{notice}</p>}
          {!!classificationResult && (
            <div className="stack" style={{ marginTop: 12 }}>
              <div className="row wrap">
                <span className="badge">Scanned: {classificationResult.scanned || 0}</span>
                <span className="badge">{classificationResult.dry_run ? 'Would correct' : 'Corrected'}: {classificationResult.changed || 0}</span>
                <span className="badge">Balance-affecting: {classificationResult.balance_affecting_changes || 0}</span>
                <span className="badge">Balance adjustment: {signedMoney(classificationResult.balance_adjustment || 0)}</span>
              </div>
              {Array.isArray(classificationResult.preview) && classificationResult.preview.length > 0 ? (
                <div className="table-wrap">
                  <table className="table dense-table">
                    <thead><tr><th>Line</th><th>From</th><th>To</th><th>Description</th><th>Amount</th><th>Balance Adjustment</th></tr></thead>
                    <tbody>
                      {classificationResult.preview.map((row) => (
                        <tr key={`classification-${row.line_id}`}>
                          <td>#{row.line_id}</td>
                          <td>{row.old_type}</td>
                          <td>{row.new_type}</td>
                          <td>{row.description || '-'}</td>
                          <td>{money(row.amount || 0)}</td>
                          <td>{signedMoney(row.balance_adjustment || 0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="small muted">No suggested corrections for this booking.</p>
              )}
            </div>
          )}
        </section>
      )}

      {booking.notes && (
        <section className="section">
          <h2>Notes</h2>
          <p>{booking.notes}</p>
        </section>
      )}
    </div>
  );
}
