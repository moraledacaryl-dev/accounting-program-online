'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  createBooking,
  createBreakfastLog,
  createGuest,
  fetchBookingChannels,
  fetchBookings,
  fetchBreakfastLogs,
  fetchMenuItems,
  fetchMenuSkus,
  fetchRatePlansEntity,
  fetchRoomTypes,
  fetchRoomsEntity,
  searchGuests,
  updateBooking,
} from '../../lib/api';
import { shouldPreventEnterSubmit } from '../../lib/formBehavior';

const PAYMENT_METHODS = ['cash', 'gcash', 'card', 'bank_transfer', 'ota_payout', 'on_account'];

const EMPTY_BOOKING_FORM = {
  guest_id: '',
  guest_name: '',
  room_id: '',
  room_type_id: '',
  rate_plan_id: '',
  channel_id: '',
  status: 'confirmed',
  check_in: '',
  check_out: '',
  gross_amount: '',
  deposit_amount: '',
  breakfast_included: '0',
  payment_method: 'cash',
  auto_post_accounting: false,
  auto_reverse_on_cancel: true,
  effective_date: '',
  notes: '',
};

const EMPTY_INLINE_GUEST = {
  first_name: '',
  last_name: '',
  full_name: '',
  phone: '',
  email: '',
  city: '',
  vip_flag: false,
  notes: '',
};

const EMPTY_BREAKFAST_FORM = {
  booking_id: '',
  meal_date: '',
  guest_name: '',
  menu_item_id: '',
  sku_id: '',
  quantity: '1',
  charge_to_room: true,
  charged_amount: '',
  payment_method: 'cash',
  auto_post_accounting: false,
  notes: '',
};

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function currency(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function maybeValue(value) {
  return value === '' ? null : value;
}

function guestLabel(guest) {
  const vip = guest.vip_flag ? 'VIP' : 'REG';
  const returning = Number(guest.booking_count || 0) > 0 ? 'returning' : 'new';
  return `${guest.full_name} · ${vip} · ${returning}`;
}

function isBookingFormSubmittable(form) {
  return !!(
    Number(form.guest_id || 0) > 0
    && Number(form.room_type_id || 0) > 0
    && Number(form.room_id || 0) > 0
    && Number(form.rate_plan_id || 0) > 0
    && Number(form.channel_id || 0) > 0
  );
}

function isBreakfastFormSubmittable(form) {
  return !!(Number(form.menu_item_id || 0) > 0 && Number(form.quantity || 0) > 0);
}

export default function BookingsPage() {
  const [bookings, setBookings] = useState([]);
  const [breakfastLogs, setBreakfastLogs] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [skus, setSkus] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [ratePlans, setRatePlans] = useState([]);
  const [channels, setChannels] = useState([]);

  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_BOOKING_FORM, effective_date: todayISO() });

  const [guestQuery, setGuestQuery] = useState('');
  const [guestSuggestions, setGuestSuggestions] = useState([]);
  const [showInlineGuestForm, setShowInlineGuestForm] = useState(false);
  const [inlineGuestForm, setInlineGuestForm] = useState({ ...EMPTY_INLINE_GUEST });

  const [breakfastForm, setBreakfastForm] = useState({ ...EMPTY_BREAKFAST_FORM, meal_date: todayISO() });

  const bookingById = useMemo(() => Object.fromEntries(bookings.map((row) => [row.id, row])), [bookings]);

  const breakfastSkus = useMemo(() => {
    const menuItemId = Number(breakfastForm.menu_item_id || 0);
    if (!menuItemId) return [];
    return skus.filter((row) => Number(row.menu_item_id) === menuItemId);
  }, [breakfastForm.menu_item_id, skus]);

  const selectedGuest = useMemo(() => {
    const id = Number(form.guest_id || 0);
    if (!id) return null;
    return guestSuggestions.find((row) => Number(row.id) === id)
      || bookings.find((row) => Number(row.guest_id || 0) === id)
      || null;
  }, [form.guest_id, guestSuggestions, bookings]);

  const filteredRooms = useMemo(() => {
    const roomTypeId = Number(form.room_type_id || 0);
    if (!roomTypeId) return rooms;
    return rooms.filter((row) => Number(row.room_type_id || 0) === roomTypeId);
  }, [rooms, form.room_type_id]);

  const filteredRatePlans = useMemo(() => {
    const roomTypeId = Number(form.room_type_id || 0);
    if (!roomTypeId) return ratePlans;
    return ratePlans.filter((row) => !row.room_type_id || Number(row.room_type_id) === roomTypeId);
  }, [ratePlans, form.room_type_id]);
  const selectedChannel = useMemo(() => {
    const channelId = Number(form.channel_id || 0);
    if (!channelId) return null;
    return channels.find((row) => Number(row.id) === channelId) || null;
  }, [channels, form.channel_id]);

  const likelyDuplicates = useMemo(() => {
    const query = `${inlineGuestForm.full_name || ''} ${inlineGuestForm.phone || ''} ${inlineGuestForm.email || ''}`.trim();
    if (!query || query.length < 2) return [];
    const q = query.toLowerCase();
    return guestSuggestions.filter((row) => {
      return String(row.full_name || '').toLowerCase().includes(q)
        || String(row.phone || '').toLowerCase().includes(q)
        || String(row.email || '').toLowerCase().includes(q);
    });
  }, [inlineGuestForm.full_name, inlineGuestForm.phone, inlineGuestForm.email, guestSuggestions]);

  async function load() {
    const [
      bookingRows,
      breakfastRows,
      menuRows,
      skuRows,
      roomTypeRows,
      roomRows,
      rateRows,
      channelRows,
    ] = await Promise.all([
      fetchBookings(),
      fetchBreakfastLogs(),
      fetchMenuItems(),
      fetchMenuSkus(),
      fetchRoomTypes(true),
      fetchRoomsEntity(true),
      fetchRatePlansEntity(true),
      fetchBookingChannels(true),
    ]);

    setBookings(Array.isArray(bookingRows) ? bookingRows : []);
    setBreakfastLogs(Array.isArray(breakfastRows) ? breakfastRows : []);
    setMenuItems(Array.isArray(menuRows) ? menuRows : []);
    setSkus(Array.isArray(skuRows) ? skuRows : []);
    setRoomTypes(Array.isArray(roomTypeRows) ? roomTypeRows : []);
    setRooms(Array.isArray(roomRows) ? roomRows : []);
    setRatePlans(Array.isArray(rateRows) ? rateRows : []);
    setChannels(Array.isArray(channelRows) ? channelRows : []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message || 'Failed to load bookings data.'));
  }, []);

  useEffect(() => {
    const q = String(guestQuery || '').trim();
    if (!q || q.length < 2) {
      setGuestSuggestions([]);
      return;
    }
    searchGuests(q, 25)
      .then((data) => setGuestSuggestions(Array.isArray(data) ? data : []))
      .catch(() => setGuestSuggestions([]));
  }, [guestQuery]);

  function resetBookingForm() {
    setEditingId(null);
    setForm({ ...EMPTY_BOOKING_FORM, effective_date: todayISO() });
    setGuestQuery('');
    setShowInlineGuestForm(false);
    setInlineGuestForm({ ...EMPTY_INLINE_GUEST });
  }

  function onRoomTypeChange(nextRoomTypeId) {
    const roomType = roomTypes.find((row) => String(row.id) === String(nextRoomTypeId));
    setForm((prev) => ({
      ...prev,
      room_type_id: nextRoomTypeId,
      room_id: '',
      rate_plan_id: '',
      breakfast_included: roomType ? String(roomType.base_capacity || prev.breakfast_included || '0') : prev.breakfast_included,
    }));
  }

  function onRatePlanChange(nextRatePlanId) {
    const plan = ratePlans.find((row) => String(row.id) === String(nextRatePlanId));
    setForm((prev) => ({
      ...prev,
      rate_plan_id: nextRatePlanId,
      breakfast_included: plan ? String(plan.breakfast_included ?? prev.breakfast_included) : prev.breakfast_included,
      gross_amount: plan && (!prev.gross_amount || Number(prev.gross_amount || 0) <= 0) ? String(plan.base_rate || '') : prev.gross_amount,
      room_type_id: plan?.room_type_id ? String(plan.room_type_id) : prev.room_type_id,
    }));
  }

  function chooseGuest(guest) {
    setForm((prev) => ({
      ...prev,
      guest_id: String(guest.id),
      guest_name: guest.full_name || prev.guest_name,
    }));
    setGuestQuery(guest.full_name || '');
  }

  async function createInlineGuest() {
    setError('');
    try {
      const payload = {
        first_name: inlineGuestForm.first_name || null,
        last_name: inlineGuestForm.last_name || null,
        full_name: inlineGuestForm.full_name || null,
        phone: inlineGuestForm.phone || null,
        email: inlineGuestForm.email || null,
        city: inlineGuestForm.city || null,
        vip_flag: !!inlineGuestForm.vip_flag,
        notes: inlineGuestForm.notes || null,
      };
      const row = await createGuest(payload);
      chooseGuest(row);
      setShowInlineGuestForm(false);
      setInlineGuestForm({ ...EMPTY_INLINE_GUEST });
      setNotice(`Guest ${row.full_name} created and selected.`);
    } catch (err) {
      setError(err.message || 'Failed to create guest.');
    }
  }

  async function submitBooking(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      if (!isBookingFormSubmittable(form)) {
        setError('Select linked guest, room type, room, rate plan, and channel before saving booking.');
        return;
      }

      const room = rooms.find((row) => String(row.id) === String(form.room_id));
      const roomType = roomTypes.find((row) => String(row.id) === String(form.room_type_id));
      const channel = channels.find((row) => String(row.id) === String(form.channel_id));

      const payload = {
        guest_id: form.guest_id ? Number(form.guest_id) : null,
        guest_name: form.guest_name || selectedGuest?.full_name || 'Unnamed Guest',
        room_id: form.room_id ? Number(form.room_id) : null,
        room_type_id: form.room_type_id ? Number(form.room_type_id) : null,
        rate_plan_id: form.rate_plan_id ? Number(form.rate_plan_id) : null,
        channel_id: form.channel_id ? Number(form.channel_id) : null,
        room_name: room ? (room.name || room.room_no) : '',
        room_type: roomType ? roomType.name : null,
        channel: channel ? channel.name : 'Walk-in',
        status: form.status,
        check_in: maybeValue(form.check_in),
        check_out: maybeValue(form.check_out),
        gross_amount: asNumber(form.gross_amount, 0),
        deposit_amount: asNumber(form.deposit_amount, 0),
        breakfast_included: Math.max(0, asNumber(form.breakfast_included, 0)),
        payment_method: form.payment_method || 'cash',
        auto_post_accounting: !!form.auto_post_accounting,
        auto_reverse_on_cancel: !!form.auto_reverse_on_cancel,
        effective_date: maybeValue(form.effective_date),
        notes: maybeValue(form.notes),
      };

      if (editingId) {
        await updateBooking(editingId, payload);
        setNotice(payload.auto_post_accounting ? 'Booking updated with accounting linkage.' : 'Booking updated.');
      } else {
        await createBooking(payload);
        setNotice(payload.auto_post_accounting ? 'Booking created and posted to accounting.' : 'Booking created.');
      }

      resetBookingForm();
      await load();
    } catch (err) {
      setError(err.message || 'Failed to save booking.');
    }
  }

  function editBooking(row) {
    setEditingId(row.id);
    setForm({
      guest_id: row.guest_id ? String(row.guest_id) : '',
      guest_name: row.guest_name || row.guest_full_name || '',
      room_id: row.room_id ? String(row.room_id) : '',
      room_type_id: row.room_type_id ? String(row.room_type_id) : '',
      rate_plan_id: row.rate_plan_id ? String(row.rate_plan_id) : '',
      channel_id: row.channel_id ? String(row.channel_id) : '',
      status: row.status || 'confirmed',
      check_in: row.check_in || '',
      check_out: row.check_out || '',
      gross_amount: row.gross_amount ?? '',
      deposit_amount: row.deposit_amount ?? '',
      breakfast_included: row.breakfast_included ?? '0',
      payment_method: 'cash',
      auto_post_accounting: false,
      auto_reverse_on_cancel: true,
      effective_date: todayISO(),
      notes: row.notes || '',
    });
    setGuestQuery(row.guest_name || row.guest_full_name || '');
    setNotice('');
    setError('');
  }

  async function lifecycleUpdate(row, nextStatus) {
    setError('');
    try {
      await updateBooking(row.id, {
        status: nextStatus,
        effective_date: todayISO(),
        auto_post_accounting: false,
        auto_reverse_on_cancel: true,
        payment_method: 'cash',
      });
      setNotice(`Booking ${row.id} marked as ${nextStatus}.`);
      await load();
    } catch (err) {
      setError(err.message || 'Failed to apply booking status change.');
    }
  }

  async function submitBreakfast(e) {
    e.preventDefault();
    setError('');
    setNotice('');
    try {
      const payload = {
        booking_id: breakfastForm.booking_id ? Number(breakfastForm.booking_id) : null,
        meal_date: breakfastForm.meal_date || todayISO(),
        guest_name: breakfastForm.guest_name || null,
        menu_item_id: Number(breakfastForm.menu_item_id || 0),
        sku_id: breakfastForm.sku_id ? Number(breakfastForm.sku_id) : null,
        quantity: asNumber(breakfastForm.quantity, 0),
        charge_to_room: !!breakfastForm.charge_to_room,
        charged_amount: breakfastForm.charged_amount === '' ? null : asNumber(breakfastForm.charged_amount, 0),
        payment_method: breakfastForm.payment_method || 'cash',
        auto_post_accounting: !!breakfastForm.auto_post_accounting,
        notes: breakfastForm.notes || null,
      };

      if (!payload.menu_item_id) {
        setError('Choose a menu item for breakfast posting.');
        return;
      }
      if (payload.quantity <= 0) {
        setError('Breakfast quantity must be greater than zero.');
        return;
      }

      await createBreakfastLog(payload);
      setNotice(payload.auto_post_accounting
        ? 'Breakfast logged with inventory + accounting linkage.'
        : 'Breakfast logged with inventory deduction.');
      setBreakfastForm({ ...EMPTY_BREAKFAST_FORM, meal_date: todayISO() });
      await load();
    } catch (err) {
      setError(err.message || 'Failed to post breakfast log.');
    }
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <div>
            <h1>Bookings</h1>
            <p className="muted">Create and manage stays with guest CRM, room setup, folios, and accounting-ready posting. This flow keeps booking, folio, and finance data connected.</p>
          </div>
          <div className="row wrap">
            <Link className="button-link secondary-link" href="/bookings/calendar">Calendar</Link>
            <Link className="button-link secondary-link" href="/guests">Open Guest CRM</Link>
            <Link className="button-link secondary-link" href="/room-folios">Open Folios</Link>
          </div>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>{editingId ? `Edit Booking #${editingId}` : 'Create Booking'}</h2>
        <form
          onSubmit={submitBooking}
          className="stack"
          onKeyDown={(event) => shouldPreventEnterSubmit(event, () => isBookingFormSubmittable(form))}
        >
          <div className="form-grid">
            <label>Find Guest
              <input
                data-enter-context="search"
                type="search"
                value={guestQuery}
                placeholder="Search name, phone, email"
                onChange={(e) => {
                  setGuestQuery(e.target.value);
                  setForm((prev) => ({ ...prev, guest_name: e.target.value, guest_id: '' }));
                }}
              />
            </label>
            <label>Guest Select
              <select
                required
                value={form.guest_id}
                onChange={(e) => {
                  const selected = guestSuggestions.find((row) => String(row.id) === e.target.value);
                  if (selected) chooseGuest(selected);
                  else setForm((prev) => ({ ...prev, guest_id: e.target.value }));
                }}
              >
                <option value="">None</option>
                {guestSuggestions.map((guest) => (
                  <option key={guest.id} value={guest.id}>{guestLabel(guest)}</option>
                ))}
              </select>
            </label>
            <label>Guest Name Snapshot<input required value={form.guest_name} onChange={(e) => setForm((prev) => ({ ...prev, guest_name: e.target.value }))} readOnly={Number(form.guest_id || 0) > 0} /></label>

            <label>Room Type
              <select required value={form.room_type_id} onChange={(e) => onRoomTypeChange(e.target.value)}>
                <option value="">Select</option>
                {roomTypes.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
            <label>Room
              <select required value={form.room_id} onChange={(e) => setForm((prev) => ({ ...prev, room_id: e.target.value }))}>
                <option value="">Select</option>
                {filteredRooms.map((row) => <option key={row.id} value={row.id}>{row.room_no} · {row.name}</option>)}
              </select>
            </label>
            <label>Rate Plan
              <select required value={form.rate_plan_id} onChange={(e) => onRatePlanChange(e.target.value)}>
                <option value="">Select</option>
                {filteredRatePlans.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>

            <label>Channel
              <select required value={form.channel_id} onChange={(e) => setForm((prev) => ({ ...prev, channel_id: e.target.value }))}>
                <option value="">Select</option>
                {channels.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
            {selectedChannel?.is_prepaid ? (
              <p className="small muted" style={{ gridColumn: '1 / -1' }}>
                Prepaid channel enabled: room charges are auto-settled in folio so the guest is not billed twice.
              </p>
            ) : null}
            <label>Status
              <select value={form.status} onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}>
                <option value="confirmed">confirmed</option>
                <option value="checked_in">checked_in</option>
                <option value="checked_out">checked_out</option>
                <option value="cancelled">cancelled</option>
              </select>
            </label>
            <label>Payment Method
              <select value={form.payment_method} onChange={(e) => setForm((prev) => ({ ...prev, payment_method: e.target.value }))}>
                {PAYMENT_METHODS.map((row) => <option key={row} value={row}>{row}</option>)}
              </select>
            </label>

            <label>Check In<input type="date" value={form.check_in} onChange={(e) => setForm((prev) => ({ ...prev, check_in: e.target.value }))} /></label>
            <label>Check Out<input type="date" value={form.check_out} onChange={(e) => setForm((prev) => ({ ...prev, check_out: e.target.value }))} /></label>
            <label>Effective Date<input type="date" value={form.effective_date} onChange={(e) => setForm((prev) => ({ ...prev, effective_date: e.target.value }))} /></label>

            <label>Gross Amount<input type="number" step="0.01" min="0" value={form.gross_amount} onChange={(e) => setForm((prev) => ({ ...prev, gross_amount: e.target.value }))} /></label>
            <label>Deposit<input type="number" step="0.01" min="0" value={form.deposit_amount} onChange={(e) => setForm((prev) => ({ ...prev, deposit_amount: e.target.value }))} /></label>
            <label>Breakfast Included<input type="number" min="0" step="1" value={form.breakfast_included} onChange={(e) => setForm((prev) => ({ ...prev, breakfast_included: e.target.value }))} /></label>

            <label>Auto Post Accounting
              <select value={String(form.auto_post_accounting)} onChange={(e) => setForm((prev) => ({ ...prev, auto_post_accounting: e.target.value === 'true' }))}>
                <option value="false">false</option>
                <option value="true">true</option>
              </select>
            </label>
            <p className="small muted" style={{ gridColumn: '1 / -1' }}>
              When enabled, this booking will post accounting entries automatically at save time.
            </p>
            <label>Auto Reverse On Cancel
              <select value={String(form.auto_reverse_on_cancel)} onChange={(e) => setForm((prev) => ({ ...prev, auto_reverse_on_cancel: e.target.value === 'true' }))}>
                <option value="true">true</option>
                <option value="false">false</option>
              </select>
            </label>
            <p className="small muted" style={{ gridColumn: '1 / -1' }}>
              Automatically reverse accounting postings if the booking is cancelled.
            </p>
          </div>

          {selectedGuest && (
            <div className="ops-alert-list" style={{ marginTop: 4 }}>
              <h3>Selected Guest Profile</h3>
              <div className="small muted">
                {selectedGuest.full_name || form.guest_name} · {selectedGuest.vip_flag ? 'VIP' : 'Standard'} ·
                {' '}{Number(selectedGuest.booking_count || 0) > 0 ? 'Returning' : 'First stay'}
              </div>
              <div className="small muted">Phone: {selectedGuest.phone || '-'} · Email: {selectedGuest.email || '-'}</div>
            </div>
          )}

          <div className="row wrap">
            <button type="button" className="secondary" onClick={() => setShowInlineGuestForm((v) => !v)}>
              {showInlineGuestForm ? 'Hide Inline Guest Form' : 'Create Guest Inline'}
            </button>
            {showInlineGuestForm && (
              <span className="small muted">Create guest now without leaving the booking page.</span>
            )}
          </div>

          {showInlineGuestForm && (
            <div className="section" style={{ marginBottom: 0 }}>
              <h3>Inline Guest Creation</h3>
              {likelyDuplicates.length > 0 && (
                <p className="error-text">Possible duplicate guest records detected ({likelyDuplicates.length}). Check Guest Select before creating.</p>
              )}
              <div className="form-grid">
                <label>First Name<input value={inlineGuestForm.first_name} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, first_name: e.target.value }))} /></label>
                <label>Last Name<input value={inlineGuestForm.last_name} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, last_name: e.target.value }))} /></label>
                <label>Full Name<input value={inlineGuestForm.full_name} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, full_name: e.target.value }))} /></label>
                <label>Phone<input value={inlineGuestForm.phone} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, phone: e.target.value }))} /></label>
                <label>Email<input type="email" value={inlineGuestForm.email} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, email: e.target.value }))} /></label>
                <label>City<input value={inlineGuestForm.city} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, city: e.target.value }))} /></label>
                <label>VIP
                  <select value={String(inlineGuestForm.vip_flag)} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, vip_flag: e.target.value === 'true' }))}>
                    <option value="false">No</option>
                    <option value="true">Yes</option>
                  </select>
                </label>
              </div>
              <label>Notes<textarea value={inlineGuestForm.notes} onChange={(e) => setInlineGuestForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
              <button type="button" onClick={createInlineGuest}>Create Guest and Select</button>
            </div>
          )}

          <label>Notes<textarea value={form.notes} onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>

          <div className="row wrap">
            <button type="submit">{editingId ? 'Update Booking' : 'Create Booking'}</button>
            {editingId && <button type="button" className="secondary" onClick={resetBookingForm}>Cancel</button>}
          </div>
        </form>
      </section>

      <section className="section">
        <h2>Booking List</h2>
        <table className="table">
          <thead><tr><th>ID</th><th>Guest</th><th>Room</th><th>Plan/Channel</th><th>Dates</th><th>Status</th><th>Amounts</th><th></th></tr></thead>
          <tbody>
            {bookings.map((row) => (
              <tr key={row.id}>
                <td>BOOK-{row.id}</td>
                <td>
                  {row.guest_full_name || row.guest_name}
                  {row.guest_vip_flag ? <span className="badge" style={{ marginLeft: 6 }}>VIP</span> : null}
                  <div className="small muted">{row.guest_phone || '-'} · {row.guest_email || '-'}</div>
                </td>
                <td>{row.room_display_name || row.room_name || '-'}<br /><span className="small muted">{row.room_type_display_name || row.room_type || '-'}</span></td>
                <td>
                  {row.rate_plan_name || '-'}
                  <br />
                  <span className="small muted">
                    {row.channel_display_name || row.channel || '-'}
                    {row.channel_is_prepaid ? ' · prepaid' : ''}
                  </span>
                </td>
                <td>{row.check_in || '-'} → {row.check_out || '-'}</td>
                <td>{row.status}</td>
	                <td>{currency(row.gross_amount || 0)}<br /><span className="small muted">Deposit {currency(row.deposit_amount || 0)}</span></td>
	                <td className="row wrap">
	                  <Link className="button-link secondary-link" href={`/bookings/${row.id}`}>Open</Link>
	                  <button type="button" className="secondary" onClick={() => editBooking(row)}>Edit</button>
	                  {!['checked_in', 'checked_out', 'cancelled'].includes(row.status) && (
	                    <button type="button" className="secondary" onClick={() => lifecycleUpdate(row, 'checked_in')}>Check In</button>
	                  )}
	                  {row.status !== 'checked_out' && row.status !== 'cancelled' && (
	                    <button type="button" className="secondary" onClick={() => lifecycleUpdate(row, 'checked_out')}>Check Out</button>
	                  )}
	                  {row.status !== 'cancelled' && row.status !== 'checked_out' && (
	                    <button type="button" className="secondary" onClick={() => lifecycleUpdate(row, 'cancelled')}>Cancel</button>
	                  )}
	                  <Link className="button-link secondary-link" href={row.primary_folio_id ? `/room-folios/${row.primary_folio_id}` : `/room-folios?booking_id=${row.id}`}>Folio</Link>
	                </td>
              </tr>
            ))}
            {!bookings.length && <tr><td colSpan="8" className="muted">No bookings yet.</td></tr>}
          </tbody>
        </table>
      </section>

      <section className="section">
        <h2>Room Breakfast Posting</h2>
        <p className="muted">Breakfast entries deduct recipe inventory and can optionally post to accounting or charge the guest folio.</p>
        <form
          onSubmit={submitBreakfast}
          className="stack"
          onKeyDown={(event) => shouldPreventEnterSubmit(event, () => isBreakfastFormSubmittable(breakfastForm))}
        >
          <div className="form-grid">
            <label>Booking
              <select value={breakfastForm.booking_id} onChange={(e) => {
                const bookingId = e.target.value;
                const booking = bookingById[Number(bookingId || 0)];
                setBreakfastForm((prev) => ({
                  ...prev,
                  booking_id: bookingId,
                  guest_name: booking ? (booking.guest_full_name || booking.guest_name || '') : prev.guest_name,
                  charged_amount: booking ? String(booking.breakfast_included || prev.charged_amount || '') : prev.charged_amount,
                }));
              }}>
                <option value="">None</option>
                {bookings.map((row) => <option key={row.id} value={row.id}>BOOK-{row.id} · {row.guest_name}</option>)}
              </select>
            </label>
            <label>Meal Date<input type="date" value={breakfastForm.meal_date} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, meal_date: e.target.value }))} /></label>
            <label>Guest Name<input value={breakfastForm.guest_name} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, guest_name: e.target.value }))} /></label>
            <label>Menu Item
              <select value={breakfastForm.menu_item_id} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, menu_item_id: e.target.value, sku_id: '' }))}>
                <option value="">Select</option>
                {menuItems.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>
            {breakfastSkus.length > 0 ? (
              <label>Variant (optional)
                <select value={breakfastForm.sku_id} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, sku_id: e.target.value }))}>
                  <option value="">Use menu item recipe</option>
                  {breakfastSkus.map((row) => <option key={row.id} value={row.id}>{row.variant_name || row.sku_code || `Variant ${row.id}`}</option>)}
                </select>
              </label>
            ) : breakfastForm.menu_item_id ? (
              <p className="muted small">This menu item has no variants; the standard recipe will be used for this breakfast log.</p>
            ) : null}
            <label>Quantity<input type="number" min="0" step="0.01" value={breakfastForm.quantity} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, quantity: e.target.value }))} /></label>
            <label>Charged Amount<input type="number" min="0" step="0.01" value={breakfastForm.charged_amount} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, charged_amount: e.target.value }))} /></label>
            <label>Charge to Room
              <select value={String(breakfastForm.charge_to_room)} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, charge_to_room: e.target.value === 'true' }))}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label>Payment Method
              <select value={breakfastForm.payment_method} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, payment_method: e.target.value }))}>
                {PAYMENT_METHODS.map((row) => <option key={row} value={row}>{row}</option>)}
              </select>
            </label>
            <label>Auto Post Accounting
              <select value={String(breakfastForm.auto_post_accounting)} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, auto_post_accounting: e.target.value === 'true' }))}>
                <option value="false">false</option>
                <option value="true">true</option>
              </select>
            </label>
          </div>
          <label>Notes<textarea value={breakfastForm.notes} onChange={(e) => setBreakfastForm((prev) => ({ ...prev, notes: e.target.value }))} /></label>
          <button type="submit">Post Breakfast Log</button>
        </form>

        <table className="table" style={{ marginTop: 16 }}>
          <thead><tr><th>No</th><th>Date</th><th>Booking</th><th>Guest</th><th>Menu</th><th>Qty</th><th>Charge</th><th>COGS</th></tr></thead>
          <tbody>
            {breakfastLogs.map((row) => (
              <tr key={row.id}>
                <td>{row.breakfast_no}</td>
                <td>{row.meal_date || '-'}</td>
                <td>{row.booking_id ? `BOOK-${row.booking_id}` : '-'}</td>
                <td>{row.guest_name || '-'}</td>
                <td>{row.menu_item_name || '-'}</td>
                <td>{Number(row.quantity || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                <td>{currency(row.charged_amount || 0)}</td>
                <td>{currency(row.cogs_amount || 0)}</td>
              </tr>
            ))}
            {!breakfastLogs.length && <tr><td colSpan="8" className="muted">No breakfast logs yet.</td></tr>}
          </tbody>
        </table>
      </section>
    </div>
  );
}
