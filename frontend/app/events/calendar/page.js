'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { request } from '../../../lib/api';
import './event-calendar.css';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const STATUS_ORDER = ['confirmed', 'quoted', 'draft', 'completed', 'cancelled'];

function localISO(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function parseISO(value) {
  if (!value) return null;
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day);
}

function monthStart(date) { return new Date(date.getFullYear(), date.getMonth(), 1); }
function addMonths(date, count) { return new Date(date.getFullYear(), date.getMonth() + count, 1); }
function money(value) { return Number(value || 0).toLocaleString('en-PH', { style: 'currency', currency: 'PHP', maximumFractionDigits: 0 }); }
function prettyTime(value) {
  if (!value) return '';
  const [hourRaw, minute = '00'] = String(value).slice(0, 5).split(':');
  const hour = Number(hourRaw);
  if (!Number.isFinite(hour)) return String(value);
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const display = hour % 12 || 12;
  return `${display}:${minute} ${suffix}`;
}
function prettyDate(value) {
  const date = parseISO(value);
  return date ? date.toLocaleDateString('en-PH', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' }) : 'Date not set';
}
function statusLabel(value) {
  const text = String(value || 'draft').replaceAll('_', ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function buildMonthDays(anchor) {
  const first = monthStart(anchor);
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - first.getDay());
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return { date, iso: localISO(date), inMonth: date.getMonth() === anchor.getMonth() };
  });
}

export default function EventCalendarPage() {
  const [anchor, setAnchor] = useState(() => monthStart(new Date()));
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [venue, setVenue] = useState('');
  const [selectedDay, setSelectedDay] = useState(() => localISO());
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [view, setView] = useState('calendar');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const grid = buildMonthDays(anchor);
      const params = new URLSearchParams({ start_date: grid[0].iso, end_date: grid[grid.length - 1].iso, limit: '1000' });
      if (status) params.set('status', status);
      if (search.trim()) params.set('q', search.trim());
      const rows = await request(`/events/?${params.toString()}`);
      setEvents(Array.isArray(rows) ? rows : []);
    } catch (err) {
      setError(err.message || 'Failed to load the event calendar.');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [anchor, status]);

  const venues = useMemo(() => Array.from(new Set(events.map((row) => String(row.venue || '').trim()).filter(Boolean))).sort(), [events]);
  const visibleEvents = useMemo(() => {
    const term = search.trim().toLowerCase();
    return events.filter((row) => {
      if (venue && String(row.venue || '') !== venue) return false;
      if (!term) return true;
      return [row.event_no, row.event_name, row.client_name, row.contact_name, row.venue, row.event_type]
        .some((value) => String(value || '').toLowerCase().includes(term));
    }).sort((a, b) => `${a.event_date || ''} ${a.start_time || ''}`.localeCompare(`${b.event_date || ''} ${b.start_time || ''}`));
  }, [events, search, venue]);

  const byDate = useMemo(() => {
    const map = new Map();
    visibleEvents.forEach((row) => {
      const key = String(row.event_date || '').slice(0, 10);
      if (!key) return;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(row);
    });
    return map;
  }, [visibleEvents]);

  const monthEvents = useMemo(() => visibleEvents.filter((row) => {
    const date = parseISO(row.event_date);
    return date && date.getFullYear() === anchor.getFullYear() && date.getMonth() === anchor.getMonth();
  }), [visibleEvents, anchor]);
  const monthConfirmed = monthEvents.filter((row) => row.status === 'confirmed').length;
  const monthBalance = monthEvents.filter((row) => !['cancelled', 'completed'].includes(row.status)).reduce((sum, row) => sum + Number(row.balance_due || 0), 0);
  const nextUpcoming = visibleEvents.find((row) => String(row.event_date || '') >= localISO() && !['cancelled', 'completed'].includes(row.status));
  const selectedDayEvents = byDate.get(selectedDay) || [];
  const selectedEvent = visibleEvents.find((row) => Number(row.id) === Number(selectedEventId)) || selectedDayEvents[0] || null;
  const grid = useMemo(() => buildMonthDays(anchor), [anchor]);

  function goToday() {
    const now = new Date();
    setAnchor(monthStart(now));
    setSelectedDay(localISO(now));
  }
  function chooseDay(iso) { setSelectedDay(iso); setSelectedEventId(null); }
  function chooseEvent(row) { setSelectedDay(String(row.event_date || '').slice(0, 10)); setSelectedEventId(row.id); }

  return (
    <div className="event-calendar-page">
      <section className="section event-calendar-hero">
        <div>
          <span className="event-calendar-eyebrow">Event operations</span>
          <h1>Event Calendar</h1>
          <p className="muted">See bookings, venue demand, event status, and outstanding balances at a glance without leaving the Events workflow.</p>
        </div>
        <div className="event-calendar-hero-actions">
          <Link className="secondary button-link" href="/events">Event list & workflow</Link>
          <Link className="button-link" href="/events">+ New event</Link>
        </div>
      </section>

      {!!error && <section className="section"><p className="error-text">{error}</p><button type="button" onClick={load}>Try again</button></section>}

      <section className="event-calendar-kpis" aria-label="Calendar summary">
        <div className="section event-calendar-kpi"><span>This month</span><strong>{monthEvents.length}</strong><small>scheduled events</small></div>
        <div className="section event-calendar-kpi"><span>Confirmed</span><strong>{monthConfirmed}</strong><small>ready for operations</small></div>
        <div className="section event-calendar-kpi"><span>Open balance</span><strong>{money(monthBalance)}</strong><small>on active events</small></div>
        <div className="section event-calendar-kpi"><span>Next event</span><strong className="event-calendar-kpi-name">{nextUpcoming?.event_name || 'None scheduled'}</strong><small>{nextUpcoming ? prettyDate(nextUpcoming.event_date) : 'No upcoming active event'}</small></div>
      </section>

      <section className="section event-calendar-toolbar">
        <div className="event-calendar-month-nav">
          <button type="button" className="secondary event-calendar-arrow" aria-label="Previous month" onClick={() => setAnchor(addMonths(anchor, -1))}>‹</button>
          <button type="button" className="secondary" onClick={goToday}>Today</button>
          <button type="button" className="secondary event-calendar-arrow" aria-label="Next month" onClick={() => setAnchor(addMonths(anchor, 1))}>›</button>
          <h2>{anchor.toLocaleDateString('en-PH', { month: 'long', year: 'numeric' })}</h2>
        </div>
        <div className="event-calendar-view-toggle" role="group" aria-label="Calendar view">
          <button type="button" className={view === 'calendar' ? 'active' : ''} onClick={() => setView('calendar')}>Month</button>
          <button type="button" className={view === 'agenda' ? 'active' : ''} onClick={() => setView('agenda')}>Agenda</button>
        </div>
        <div className="event-calendar-filters">
          <label><span>Status</span><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option>{STATUS_ORDER.map((item) => <option key={item} value={item}>{statusLabel(item)}</option>)}</select></label>
          <label><span>Venue</span><select value={venue} onChange={(e) => setVenue(e.target.value)}><option value="">All venues</option>{venues.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
          <label className="event-calendar-search"><span>Search</span><input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') load(); }} placeholder="Event, client, venue…" /></label>
          <button type="button" className="secondary event-calendar-refresh" onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Refresh'}</button>
        </div>
      </section>

      {view === 'calendar' ? (
        <div className="event-calendar-layout">
          <section className="section event-calendar-shell">
            <div className="event-calendar-weekdays">{WEEKDAYS.map((day) => <div key={day}>{day}</div>)}</div>
            <div className="event-calendar-grid">
              {grid.map((day) => {
                const rows = byDate.get(day.iso) || [];
                const isToday = day.iso === localISO();
                const isSelected = day.iso === selectedDay;
                return <button key={day.iso} type="button" className={`event-calendar-day ${day.inMonth ? '' : 'outside'} ${isToday ? 'today' : ''} ${isSelected ? 'selected' : ''}`} onClick={() => chooseDay(day.iso)}>
                  <div className="event-calendar-day-head"><span className="event-calendar-date-number">{day.date.getDate()}</span>{isToday && <span className="event-calendar-today-label">Today</span>}</div>
                  <div className="event-calendar-day-events">
                    {rows.slice(0, 3).map((row) => <span key={row.id} role="button" tabIndex={0} className={`event-calendar-event status-${row.status || 'draft'}`} onClick={(e) => { e.stopPropagation(); chooseEvent(row); }} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); chooseEvent(row); } }}>
                      <span className="event-calendar-dot" />
                      <span className="event-calendar-event-text"><strong>{row.start_time ? prettyTime(row.start_time) : 'All day'}</strong> {row.event_name || row.client_name || row.event_no}</span>
                    </span>)}
                    {rows.length > 3 && <span className="event-calendar-more">+{rows.length - 3} more</span>}
                  </div>
                </button>;
              })}
            </div>
          </section>

          <aside className="section event-calendar-inspector">
            <div className="event-calendar-inspector-head"><div><span className="event-calendar-eyebrow">{prettyDate(selectedDay)}</span><h2>{selectedDayEvents.length ? `${selectedDayEvents.length} event${selectedDayEvents.length === 1 ? '' : 's'}` : 'No events'}</h2></div></div>
            {selectedDayEvents.length > 1 && <div className="event-calendar-day-list">{selectedDayEvents.map((row) => <button type="button" key={row.id} className={Number(selectedEvent?.id) === Number(row.id) ? 'active' : ''} onClick={() => setSelectedEventId(row.id)}><span className={`event-calendar-dot status-${row.status || 'draft'}`} />{prettyTime(row.start_time) || 'All day'} · {row.event_name || row.client_name}</button>)}</div>}
            {selectedEvent ? <div className="event-calendar-detail">
              <div className="event-calendar-detail-title"><div><span className={`event-calendar-status status-${selectedEvent.status || 'draft'}`}>{statusLabel(selectedEvent.status)}</span><h3>{selectedEvent.event_name || selectedEvent.event_no}</h3><p>{selectedEvent.client_name || 'Client not set'}</p></div></div>
              <dl>
                <div><dt>Time</dt><dd>{prettyTime(selectedEvent.start_time) || 'Not set'}{selectedEvent.end_time ? ` – ${prettyTime(selectedEvent.end_time)}` : ''}</dd></div>
                <div><dt>Venue</dt><dd>{selectedEvent.venue || 'Not set'}</dd></div>
                <div><dt>Guests</dt><dd>{Number(selectedEvent.guest_count || 0).toLocaleString()}</dd></div>
                <div><dt>Event type</dt><dd>{selectedEvent.event_type || 'Not set'}</dd></div>
                <div><dt>Total</dt><dd>{money(selectedEvent.total_amount)}</dd></div>
                <div><dt>Balance due</dt><dd className={Number(selectedEvent.balance_due || 0) > 0 ? 'event-calendar-balance' : ''}>{money(selectedEvent.balance_due)}</dd></div>
              </dl>
              {selectedEvent.notes && <div className="event-calendar-notes"><span>Notes</span><p>{selectedEvent.notes}</p></div>}
              <Link className="button-link event-calendar-manage" href="/events">Manage in Events Workflow</Link>
            </div> : <div className="event-calendar-empty"><strong>Clear day</strong><p>No event is scheduled on this date.</p><Link href="/events">Create an event</Link></div>}
          </aside>
        </div>
      ) : (
        <section className="section event-calendar-agenda">
          <div className="event-calendar-agenda-head"><div><h2>{anchor.toLocaleDateString('en-PH', { month: 'long', year: 'numeric' })} agenda</h2><p className="muted">Chronological event plan with operational and payment context.</p></div><span className="badge">{monthEvents.length} events</span></div>
          {monthEvents.length ? <div className="event-calendar-agenda-list">{monthEvents.map((row) => <button type="button" key={row.id} onClick={() => { chooseEvent(row); setView('calendar'); }}>
            <div className="event-calendar-agenda-date"><strong>{parseISO(row.event_date)?.getDate()}</strong><span>{parseISO(row.event_date)?.toLocaleDateString('en-PH', { weekday: 'short' })}</span></div>
            <div className="event-calendar-agenda-main"><div><span className={`event-calendar-status status-${row.status || 'draft'}`}>{statusLabel(row.status)}</span><strong>{row.event_name || row.event_no}</strong></div><span>{row.client_name || 'Client not set'} · {row.venue || 'Venue not set'}</span></div>
            <div className="event-calendar-agenda-meta"><strong>{prettyTime(row.start_time) || 'Time not set'}</strong><span>{Number(row.guest_count || 0)} guests</span></div>
            <div className="event-calendar-agenda-money"><strong>{money(row.total_amount)}</strong><span>{money(row.balance_due)} due</span></div>
          </button>)}</div> : <div className="event-calendar-empty"><strong>No events this month</strong><p>Change filters, move to another month, or create a new event.</p><Link href="/events">Create an event</Link></div>}
        </section>
      )}
    </div>
  );
}
