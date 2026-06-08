'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  cancelEvent,
  completeEvent,
  confirmEvent,
  createEvent,
  fetchEvents,
  recordEventPayment,
  updateEvent,
} from '../../lib/api';
import { fetchFinancialAccounts } from '../../lib/cashflowApi';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function emptyLine() {
  return { line_type: 'package', description: '', quantity: 1, unit_price: 0, total_amount: '', notes: '', sort_order: 0 };
}

function emptyForm() {
  return {
    id: null,
    event_no: '',
    event_name: '',
    client_name: '',
    contact_name: '',
    contact_phone: '',
    contact_email: '',
    event_type: '',
    event_date: todayISO(),
    start_time: '',
    end_time: '',
    venue: '',
    guest_count: 0,
    package_name: '',
    status: 'draft',
    quote_sent_at: '',
    deposit_required: '',
    deposit_due_date: '',
    discount_amount: '',
    tax_amount: '',
    notes: '',
    lines: [emptyLine()],
  };
}

function toForm(row) {
  return {
    ...emptyForm(),
    ...row,
    deposit_required: row.deposit_required || '',
    discount_amount: row.discount_amount || '',
    tax_amount: row.tax_amount || '',
    lines: row.lines?.length ? row.lines.map((line) => ({ ...line })) : [emptyLine()],
  };
}

function payloadFromForm(form) {
  return {
    event_no: form.event_no || null,
    event_name: form.event_name,
    client_name: form.client_name,
    contact_name: form.contact_name || null,
    contact_phone: form.contact_phone || null,
    contact_email: form.contact_email || null,
    event_type: form.event_type || null,
    event_date: form.event_date || null,
    start_time: form.start_time || null,
    end_time: form.end_time || null,
    venue: form.venue || null,
    guest_count: Number(form.guest_count || 0),
    package_name: form.package_name || null,
    status: form.status || 'draft',
    quote_sent_at: form.quote_sent_at || null,
    deposit_required: Number(form.deposit_required || 0),
    deposit_due_date: form.deposit_due_date || null,
    discount_amount: Number(form.discount_amount || 0),
    tax_amount: Number(form.tax_amount || 0),
    notes: form.notes || null,
    lines: (form.lines || [])
      .filter((line) => String(line.description || '').trim())
      .map((line, index) => ({
        id: line.id || null,
        line_type: line.line_type || 'package',
        description: line.description,
        quantity: Number(line.quantity || 0),
        unit_price: Number(line.unit_price || 0),
        total_amount: line.total_amount === '' || line.total_amount === null ? null : Number(line.total_amount || 0),
        notes: line.notes || null,
        sort_order: index,
      })),
  };
}

export default function EventsPage() {
  const [events, setEvents] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [filters, setFilters] = useState({ status: '', q: '' });
  const [form, setForm] = useState(emptyForm());
  const [paymentForm, setPaymentForm] = useState({
    payment_date: todayISO(),
    amount: '',
    financial_account_id: '',
    payment_method: 'cash',
    reference_no: '',
    notes: '',
  });
  const [actionNote, setActionNote] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function load(nextFilters = filters) {
    const [rows, accountRows] = await Promise.all([
      fetchEvents({ ...nextFilters, limit: 500 }),
      fetchFinancialAccounts({ only_active: true }),
    ]);
    setEvents(Array.isArray(rows) ? rows : []);
    setAccounts(Array.isArray(accountRows) ? accountRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load events.'));
  }, []);

  const selected = useMemo(() => events.find((row) => Number(row.id) === Number(form.id)) || null, [events, form.id]);

  const summary = useMemo(() => {
    const activeRows = events.filter((row) => !['cancelled', 'completed'].includes(row.status));
    return {
      active: activeRows.length,
      confirmed: events.filter((row) => row.status === 'confirmed').length,
      balanceDue: activeRows.reduce((sum, row) => sum + Number(row.balance_due || 0), 0),
      totalPipeline: activeRows.reduce((sum, row) => sum + Number(row.total_amount || 0), 0),
    };
  }, [events]);

  function updateLine(index, field, value) {
    setForm((prev) => ({
      ...prev,
      lines: prev.lines.map((line, idx) => (idx === index ? { ...line, [field]: value } : line)),
    }));
  }

  async function refreshAfter(message, updated = null) {
    await load();
    if (updated?.id) setForm(toForm(updated));
    setNotice(message);
  }

  async function saveEvent(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    setLoading(true);
    try {
      const payload = payloadFromForm(form);
      const saved = form.id ? await updateEvent(form.id, payload) : await createEvent(payload);
      await refreshAfter(form.id ? 'Event updated.' : 'Event created.', saved);
    } catch (err) {
      setError(err.message || 'Failed to save event.');
    } finally {
      setLoading(false);
    }
  }

  async function runAction(action) {
    if (!form.id) return;
    setError('');
    setNotice('');
    setLoading(true);
    try {
      const payload = { action_date: todayISO(), note: actionNote || null };
      let updated = null;
      if (action === 'confirm') updated = await confirmEvent(form.id, payload);
      if (action === 'complete') updated = await completeEvent(form.id, payload);
      if (action === 'cancel') updated = await cancelEvent(form.id, payload);
      setActionNote('');
      await refreshAfter(`Event ${action}ed.`, updated);
    } catch (err) {
      setError(err.message || `Failed to ${action} event.`);
    } finally {
      setLoading(false);
    }
  }

  async function submitPayment(e) {
    e.preventDefault();
    if (!form.id) return;
    setError('');
    setNotice('');
    setLoading(true);
    try {
      const updated = await recordEventPayment(form.id, {
        payment_date: paymentForm.payment_date || todayISO(),
        amount: Number(paymentForm.amount || 0),
        financial_account_id: Number(paymentForm.financial_account_id || 0),
        payment_method: paymentForm.payment_method || 'cash',
        reference_no: paymentForm.reference_no || null,
        notes: paymentForm.notes || null,
      });
      setPaymentForm((prev) => ({ ...prev, amount: '', reference_no: '', notes: '' }));
      await refreshAfter('Event payment recorded and applied to AR.', updated);
    } catch (err) {
      setError(err.message || 'Failed to record event payment.');
    } finally {
      setLoading(false);
    }
  }

  function isEventSubmittable() {
    return !!(form.event_name && form.client_name);
  }

  function isPaymentSubmittable() {
    return !!(form.id && Number(paymentForm.amount || 0) > 0 && Number(paymentForm.financial_account_id || 0) > 0);
  }

  return (
    <div>
      <section className="section">
        <h1>Events Workflow</h1>
        <p className="muted">Create event quotes, confirm them into accounting receivables, collect deposits/balances, and keep the front desk follow-up list clean.</p>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
        <div className="row wrap">
          <span className="badge">Active Events {summary.active}</span>
          <span className="badge">Confirmed {summary.confirmed}</span>
          <span className="badge">Pipeline {currency(summary.totalPipeline)}</span>
          <span className="badge">Balance Due {currency(summary.balanceDue)}</span>
        </div>
      </section>

      <div className="grid">
        <section className="section">
          <div className="row space-between wrap">
            <h2>Event List</h2>
            <button type="button" className="secondary" onClick={() => setForm(emptyForm())}>New Event</button>
          </div>
          <div className="form-grid">
            <label>
              Status
              <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}>
                <option value="">All statuses</option>
                <option value="draft">Draft</option>
                <option value="quoted">Quoted</option>
                <option value="confirmed">Confirmed</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </label>
            <label>
              Search
              <input value={filters.q} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} placeholder="Client, event, venue, event no" />
            </label>
          </div>
          <div className="row wrap" style={{ marginTop: 10 }}>
            <button type="button" onClick={() => load()}>Refresh</button>
            <button type="button" className="secondary" onClick={() => { const next = { status: '', q: '' }; setFilters(next); load(next); }}>Clear Filters</button>
          </div>
          <div className="table-wrap" style={{ marginTop: 10 }}>
            <table className="table dense-table">
              <thead><tr><th>Event</th><th>Date</th><th>Status</th><th>Total</th><th>Balance</th></tr></thead>
              <tbody>
                {events.map((row) => (
                  <tr key={row.id} onClick={() => setForm(toForm(row))} style={{ cursor: 'pointer' }}>
                    <td>
                      <strong>{row.event_no}</strong>
                      <div className="small">{row.event_name}</div>
                      <div className="small muted">{row.client_name}</div>
                    </td>
                    <td>{row.event_date || '-'}</td>
                    <td><span className="badge">{row.status}</span></td>
                    <td>{currency(row.total_amount)}</td>
                    <td>{currency(row.balance_due)}</td>
                  </tr>
                ))}
                {!events.length && <tr><td colSpan="5" className="muted">No events found.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="section">
          <h2>{form.id ? `Edit ${form.event_no}` : 'New Event Quote'}</h2>
          <form onSubmit={saveEvent} onKeyDown={(event) => shouldPreventEnterSubmit(event, isEventSubmittable)}>
            <div className="form-grid">
              <label>Event Name<input value={form.event_name || ''} onChange={(e) => setForm((f) => ({ ...f, event_name: e.target.value }))} /></label>
              <label>Client Name<input value={form.client_name || ''} onChange={(e) => setForm((f) => ({ ...f, client_name: e.target.value }))} /></label>
              <label>Event No<input value={form.event_no || ''} onChange={(e) => setForm((f) => ({ ...f, event_no: e.target.value }))} placeholder="Auto-generated if blank" /></label>
              <label>Status<select value={form.status || 'draft'} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}><option value="draft">Draft</option><option value="quoted">Quoted</option><option value={form.status || 'draft'}>{form.status || 'draft'}</option></select></label>
              <label>Event Type<input value={form.event_type || ''} onChange={(e) => setForm((f) => ({ ...f, event_type: e.target.value }))} placeholder="Wedding, seminar, private dinner" /></label>
              <label>Venue<input value={form.venue || ''} onChange={(e) => setForm((f) => ({ ...f, venue: e.target.value }))} /></label>
              <label>Event Date<input type="date" value={form.event_date || ''} onChange={(e) => setForm((f) => ({ ...f, event_date: e.target.value }))} /></label>
              <label>Start Time<input type="time" value={form.start_time || ''} onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))} /></label>
              <label>End Time<input type="time" value={form.end_time || ''} onChange={(e) => setForm((f) => ({ ...f, end_time: e.target.value }))} /></label>
              <label>Guests<input type="number" min="0" value={form.guest_count || 0} onChange={(e) => setForm((f) => ({ ...f, guest_count: e.target.value }))} /></label>
              <label>Package<input value={form.package_name || ''} onChange={(e) => setForm((f) => ({ ...f, package_name: e.target.value }))} /></label>
              <label>Quote Sent<input type="date" value={form.quote_sent_at || ''} onChange={(e) => setForm((f) => ({ ...f, quote_sent_at: e.target.value }))} /></label>
              <label>Deposit Required<input type="number" step="0.01" value={form.deposit_required || ''} onChange={(e) => setForm((f) => ({ ...f, deposit_required: e.target.value }))} /></label>
              <label>Deposit Due<input type="date" value={form.deposit_due_date || ''} onChange={(e) => setForm((f) => ({ ...f, deposit_due_date: e.target.value }))} /></label>
              <label>Discount<input type="number" step="0.01" value={form.discount_amount || ''} onChange={(e) => setForm((f) => ({ ...f, discount_amount: e.target.value }))} /></label>
              <label>Tax / Service Charge<input type="number" step="0.01" value={form.tax_amount || ''} onChange={(e) => setForm((f) => ({ ...f, tax_amount: e.target.value }))} /></label>
              <label>Contact Name<input value={form.contact_name || ''} onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))} /></label>
              <label>Contact Phone<input value={form.contact_phone || ''} onChange={(e) => setForm((f) => ({ ...f, contact_phone: e.target.value }))} /></label>
              <label>Contact Email<input value={form.contact_email || ''} onChange={(e) => setForm((f) => ({ ...f, contact_email: e.target.value }))} /></label>
            </div>
            <label>Notes<textarea value={form.notes || ''} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>

            <div className="event-quote-heading">
              <h3>Quote Lines</h3>
              <span className="small muted">Long package names and descriptions wrap inside the quote card.</span>
            </div>
            <div className="event-quote-lines">
              {(form.lines || []).map((line, index) => (
                <div key={index} className="event-quote-line-card">
                  <label>
                    Type
                    <select value={line.line_type || 'package'} onChange={(e) => updateLine(index, 'line_type', e.target.value)}>
                      <option value="package">Package</option>
                      <option value="venue">Venue</option>
                      <option value="food">Food</option>
                      <option value="beverage">Beverage</option>
                      <option value="addon">Add-on</option>
                      <option value="discount">Discount</option>
                    </select>
                  </label>
                  <label className="event-quote-description">
                    Description
                    <input value={line.description || ''} onChange={(e) => updateLine(index, 'description', e.target.value)} placeholder="Package, dish, venue setup, add-on, or discount" />
                  </label>
                  <label>
                    Qty
                    <input type="number" step="0.01" value={line.quantity ?? 1} onChange={(e) => updateLine(index, 'quantity', e.target.value)} />
                  </label>
                  <label>
                    Unit Price
                    <input type="number" step="0.01" value={line.unit_price ?? 0} onChange={(e) => updateLine(index, 'unit_price', e.target.value)} />
                  </label>
                  <label>
                    Total Override
                    <input type="number" step="0.01" value={line.total_amount ?? ''} onChange={(e) => updateLine(index, 'total_amount', e.target.value)} placeholder="Qty x price" />
                  </label>
                  <div className="event-quote-line-actions">
                    <button type="button" className="secondary" onClick={() => setForm((f) => ({ ...f, lines: f.lines.filter((_, idx) => idx !== index) }))}>Remove</button>
                  </div>
                </div>
              ))}
            </div>
            <button type="button" className="secondary" onClick={() => setForm((f) => ({ ...f, lines: [...(f.lines || []), emptyLine()] }))}>Add Line</button>
            <div className="row wrap" style={{ marginTop: 12 }}>
              <button type="submit" disabled={loading}>{form.id ? 'Save Event' : 'Create Event'}</button>
              <span className="badge">Saved Total {currency(selected?.total_amount)}</span>
              <span className="badge">Paid {currency(selected?.deposit_paid)}</span>
              <span className="badge">Balance {currency(selected?.balance_due)}</span>
            </div>
          </form>
        </section>
      </div>

      {form.id && (
        <div className="grid">
          <section className="section">
            <h2>Workflow Actions</h2>
            <p className="muted">Confirming creates the event income record, AR receivable, and journal entry. Payments settle that AR balance.</p>
            <label>Action Note<textarea value={actionNote} onChange={(e) => setActionNote(e.target.value)} placeholder="Optional note for confirm, complete, or cancel" /></label>
            <div className="row wrap">
              <button type="button" onClick={() => runAction('confirm')} disabled={loading || ['confirmed', 'completed', 'cancelled'].includes(form.status)}>Confirm & Post AR</button>
              <button type="button" className="secondary" onClick={() => runAction('complete')} disabled={loading || ['draft', 'cancelled', 'completed'].includes(form.status)}>Mark Completed</button>
              <button type="button" className="danger" onClick={() => runAction('cancel')} disabled={loading || ['completed', 'cancelled'].includes(form.status)}>Cancel Event</button>
            </div>
            <div className="row wrap" style={{ marginTop: 10 }}>
              <span className="badge">Record ID {selected?.record_id || '-'}</span>
              <span className="badge">Receivable ID {selected?.receivable_id || '-'}</span>
              <span className="badge">Receivable {selected?.receivable_status || '-'}</span>
            </div>
          </section>

          <section className="section">
            <h2>Collect Event Payment</h2>
            <form onSubmit={submitPayment} onKeyDown={(event) => shouldPreventEnterSubmit(event, isPaymentSubmittable)}>
              <div className="form-grid">
                <label>Payment Date<input type="date" value={paymentForm.payment_date} onChange={(e) => setPaymentForm((f) => ({ ...f, payment_date: e.target.value }))} /></label>
                <label>Amount<input type="number" min="0.01" step="0.01" value={paymentForm.amount} onChange={(e) => setPaymentForm((f) => ({ ...f, amount: e.target.value }))} /></label>
                <label>Account<select value={paymentForm.financial_account_id} onChange={(e) => setPaymentForm((f) => ({ ...f, financial_account_id: e.target.value }))}><option value="">Select account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {currency(account.current_balance)}</option>)}</select></label>
                <label>Method<input value={paymentForm.payment_method} onChange={(e) => setPaymentForm((f) => ({ ...f, payment_method: e.target.value }))} /></label>
                <label>Reference<input value={paymentForm.reference_no} onChange={(e) => setPaymentForm((f) => ({ ...f, reference_no: e.target.value }))} /></label>
              </div>
              <label>Notes<textarea value={paymentForm.notes} onChange={(e) => setPaymentForm((f) => ({ ...f, notes: e.target.value }))} /></label>
              <button type="submit" disabled={loading || !isPaymentSubmittable()}>Record Payment</button>
            </form>
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table className="table dense-table">
                <thead><tr><th>Date</th><th>Amount</th><th>Account</th><th>Ref</th></tr></thead>
                <tbody>
                  {(selected?.payments || []).map((payment) => (
                    <tr key={payment.id}>
                      <td>{payment.payment_date}</td>
                      <td>{currency(payment.amount)}</td>
                      <td>{payment.financial_account_name || '-'}</td>
                      <td>{payment.reference_no || '-'}</td>
                    </tr>
                  ))}
                  {!selected?.payments?.length && <tr><td colSpan="4" className="muted">No payments yet.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
