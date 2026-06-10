'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import {
  fetchBookingCalendar,
  fetchBookingChannels,
  fetchRoomsEntity,
} from '../../../lib/api';
import { stayIncludesDay } from '../../../lib/stays';

const STATUS_ALL = '__all__';

function isoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

function startOfCalendarMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date, count) {
  return new Date(date.getFullYear(), date.getMonth() + count, 1);
}

function buildCalendarDays(monthDate) {
  const first = startOfCalendarMonth(monthDate);
  const start = new Date(first);
  start.setDate(first.getDate() - first.getDay());
  return Array.from({ length: 42 }, (_, idx) => {
    const day = new Date(start);
    day.setDate(start.getDate() + idx);
    return day;
  });
}

function statusClass(status) {
  const value = String(status || '').toLowerCase();
  if (value === 'cancelled' || value === 'no_show') return 'status rejected';
  if (value === 'checked_in') return 'status approved';
  if (value === 'checked_out') return 'status draft';
  return 'status pending';
}

export default function BookingCalendarPage() {
  const [monthDate, setMonthDate] = useState(startOfCalendarMonth(new Date()));
  const [rows, setRows] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [channels, setChannels] = useState([]);
  const [roomFilter, setRoomFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState(STATUS_ALL);
  const [channelFilter, setChannelFilter] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const days = useMemo(() => buildCalendarDays(monthDate), [monthDate]);
  const range = useMemo(() => ({
    start_date: isoDate(days[0]),
    end_date: isoDate(days[days.length - 1]),
  }), [days]);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [bookingRows, roomRows, channelRows] = await Promise.all([
        fetchBookingCalendar({
          ...range,
          room_id: roomFilter ? Number(roomFilter) : undefined,
          status: statusFilter !== STATUS_ALL ? statusFilter : undefined,
          channel_id: channelFilter ? Number(channelFilter) : undefined,
        }),
        fetchRoomsEntity(true),
        fetchBookingChannels(true),
      ]);
      setRows(Array.isArray(bookingRows) ? bookingRows : []);
      setRooms(Array.isArray(roomRows) ? roomRows : []);
      setChannels(Array.isArray(channelRows) ? channelRows : []);
    } catch (err) {
      setError(err.message || 'Failed to load booking calendar.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [range.start_date, range.end_date, roomFilter, statusFilter, channelFilter]);

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <div>
            <h1>Booking Calendar</h1>
            <p className="muted">Browse past, current, and future stays by month.</p>
          </div>
          <div className="row wrap">
            <Link className="button-link secondary-link" href="/bookings">Booking List</Link>
            <button type="button" className="secondary" onClick={() => setMonthDate(addMonths(monthDate, -1))}>Previous</button>
            <button type="button" className="secondary" onClick={() => setMonthDate(startOfCalendarMonth(new Date()))}>Today</button>
            <button type="button" className="secondary" onClick={() => setMonthDate(addMonths(monthDate, 1))}>Next</button>
          </div>
        </div>
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <div className="row wrap" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <h2>{monthDate.toLocaleString(undefined, { month: 'long', year: 'numeric' })}</h2>
          <div className="row wrap">
            <label style={{ minWidth: 180 }}>
              Room
              <select value={roomFilter} onChange={(e) => setRoomFilter(e.target.value)}>
                <option value="">All rooms</option>
                {rooms.map((row) => <option key={row.id} value={row.id}>{row.room_no} · {row.name}</option>)}
              </select>
            </label>
            <label style={{ minWidth: 160 }}>
              Status
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
                <option value={STATUS_ALL}>All statuses</option>
                <option value="confirmed">confirmed</option>
                <option value="checked_in">checked_in</option>
                <option value="checked_out">checked_out</option>
                <option value="cancelled">cancelled</option>
                <option value="no_show">no_show</option>
              </select>
            </label>
            <label style={{ minWidth: 180 }}>
              Channel
              <select value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)}>
                <option value="">All channels</option>
                {channels.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
          </div>
        </div>
        <div className="calendar-grid">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((label) => (
            <div key={label} className="calendar-weekday">{label}</div>
          ))}
          {days.map((day) => {
            const dayISO = isoDate(day);
            const inMonth = monthKey(day) === monthKey(monthDate);
            const matchingRows = rows.filter((row) => stayIncludesDay(row, dayISO));
            const dayRows = matchingRows.slice(0, 5);
            return (
              <div key={dayISO} className={`calendar-day${inMonth ? '' : ' muted-day'}`}>
                <div className="calendar-date">{day.getDate()}</div>
                <div className="calendar-events">
                  {dayRows.map((row) => (
                    <Link key={`${dayISO}-${row.id}`} className="calendar-event" href={`/bookings/${row.id}`}>
                      <span className={statusClass(row.status)}>{row.status || 'confirmed'}</span>
                      <strong>{row.guest_full_name || row.guest_name || `BOOK-${row.id}`}</strong>
                      <span>{row.room_display_name || row.room_name || 'Unassigned'} · {row.channel_display_name || row.channel || 'Channel'}</span>
                    </Link>
                  ))}
                  {matchingRows.length > 5 && (
                    <span className="small muted">+{matchingRows.length - 5} more</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        {loading && <p className="muted">Loading calendar...</p>}
      </section>
    </div>
  );
}
