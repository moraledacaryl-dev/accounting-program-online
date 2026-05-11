'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  executeBeds24Reset,
  fetchBeds24MappingHelpers,
  fetchBeds24IntegrationSettings,
  fetchBeds24SyncState,
  fetchBeds24SyncLogs,
  previewBeds24Reset,
  rebuildBeds24BookingMirror,
  syncBeds24Backfill,
  syncBeds24Booking,
  syncBeds24Recent,
  testBeds24IntegrationConnection,
  updateBeds24IntegrationSettings,
} from '../../../lib/api';
import { useCurrentUser } from '../../../lib/useCurrentUser';

const DEFAULT_SETTINGS = {
  enabled: false,
  api_base_url: 'https://beds24.com/api/v2',
  access_token: '',
  refresh_token: '',
  invite_code: '',
  webhook_enabled: false,
  webhook_secret: '',
  webhook_require_secret: true,
  manual_sync_only: true,
  auto_create_guest: true,
  auto_create_folio_mirror: false,
  auto_create_receivable_mirror: false,
  auto_link_room: true,
  auto_link_channel: true,
  auto_link_property: false,
  fallback_unknown_room_behavior: 'leave_unlinked',
  fallback_unknown_channel_behavior: 'leave_unlinked',
  include_invoice_items: true,
  log_verbosity: 'normal',
  room_map_by_room_id: {},
  room_map_by_unit_id: {},
  channel_map_by_source: {},
  property_map_by_id: {},
};

const RESET_MODE_OPTIONS = [
  { value: 'beds24_imported_bookings', label: 'Reset Beds24 Imported Bookings Only' },
  { value: 'beds24_imported_folios', label: 'Reset Beds24 Imported Folio Mirror Only' },
  { value: 'beds24_imported_guests_unlinked', label: 'Reset Beds24 Guests (Unlinked Only)' },
  { value: 'beds24_all', label: 'Reset Beds24 Bookings + Folios + Maps + Logs' },
  { value: 'local_test_full', label: 'Full Local Test Reset (Bookings + Guests)' },
];

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function addMonthsISO(months) {
  const date = new Date();
  date.setMonth(date.getMonth() + months);
  return date.toISOString().slice(0, 10);
}

function pretty(value) {
  return JSON.stringify(value || {}, null, 2);
}

function parseJsonObject(label, raw) {
  const text = String(raw || '').trim();
  if (!text) return {};
  let parsed = null;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed;
}

function syncStatusClass(status) {
  const value = String(status || '').toLowerCase();
  if (value === 'success' || value === 'synced') return 'status approved';
  if (value === 'partial') return 'status pending';
  if (value === 'error' || value === 'failed') return 'status rejected';
  return 'status draft';
}

export default function Beds24IntegrationPage() {
  const { can } = useCurrentUser();
  const [settings, setSettings] = useState({ ...DEFAULT_SETTINGS });
  const [roomMapByRoomIdText, setRoomMapByRoomIdText] = useState(pretty(DEFAULT_SETTINGS.room_map_by_room_id));
  const [roomMapByUnitIdText, setRoomMapByUnitIdText] = useState(pretty(DEFAULT_SETTINGS.room_map_by_unit_id));
  const [channelMapText, setChannelMapText] = useState(pretty(DEFAULT_SETTINGS.channel_map_by_source));
  const [propertyMapText, setPropertyMapText] = useState(pretty(DEFAULT_SETTINGS.property_map_by_id));
  const [logs, setLogs] = useState([]);
  const [syncStateRows, setSyncStateRows] = useState([]);
  const [mappingHelpers, setMappingHelpers] = useState({ rooms: [], channels: [] });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [testResult, setTestResult] = useState(null);
  const [syncBookingId, setSyncBookingId] = useState('');
  const [resetMode, setResetMode] = useState('beds24_imported_bookings');
  const [resetPreview, setResetPreview] = useState(null);
  const [resetConfirmation, setResetConfirmation] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [recentSyncForm, setRecentSyncForm] = useState({
    limit: 25,
    status: '',
    filter: '',
    include_invoice_items: true,
  });
  const [backfillRunning, setBackfillRunning] = useState(false);
  const [backfillResult, setBackfillResult] = useState(null);
  const [backfillForm, setBackfillForm] = useState({
    from_date: addMonthsISO(-3),
    to_date: todayISO(),
    property_id: '',
    statuses: '',
    include_invoice_items: true,
    dry_run: true,
    chunk_days: 31,
    request_delay_seconds: 4,
  });

  const canManage = can('integrations.manage');
  const canSync = can('integrations.sync');
  const canViewLogs = can('integrations.logs.view') || canManage || canSync;

  const lastLogTimestamp = useMemo(() => logs[0]?.created_at || null, [logs]);

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [settingsRes, logsRes] = await Promise.all([
        fetchBeds24IntegrationSettings(),
        canViewLogs ? fetchBeds24SyncLogs({ limit: 100 }) : Promise.resolve([]),
      ]);
      const [helpersRes, stateRes] = await Promise.all([
        fetchBeds24MappingHelpers(),
        canViewLogs ? fetchBeds24SyncState({ limit: 100 }) : Promise.resolve([]),
      ]);
      const nextSettings = { ...DEFAULT_SETTINGS, ...(settingsRes?.settings || {}) };
      setSettings(nextSettings);
      setRoomMapByRoomIdText(pretty(nextSettings.room_map_by_room_id));
      setRoomMapByUnitIdText(pretty(nextSettings.room_map_by_unit_id));
      setChannelMapText(pretty(nextSettings.channel_map_by_source));
      setPropertyMapText(pretty(nextSettings.property_map_by_id));
      setLogs(Array.isArray(logsRes) ? logsRes : []);
      setSyncStateRows(Array.isArray(stateRes) ? stateRes : []);
      setMappingHelpers({
        rooms: Array.isArray(helpersRes?.rooms) ? helpersRes.rooms : [],
        channels: Array.isArray(helpersRes?.channels) ? helpersRes.channels : [],
      });
    } catch (err) {
      setError(err.message || 'Failed to load Beds24 integration settings.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [canViewLogs]);

  function patchSettings(patch) {
    setSettings((prev) => ({ ...prev, ...patch }));
  }

  async function refreshDebugData() {
    if (!canViewLogs) return;
    const [logsRes, stateRes] = await Promise.all([
      fetchBeds24SyncLogs({ limit: 100 }),
      fetchBeds24SyncState({ limit: 100 }),
    ]);
    setLogs(Array.isArray(logsRes) ? logsRes : []);
    setSyncStateRows(Array.isArray(stateRes) ? stateRes : []);
  }

  async function saveSettings() {
    if (!canManage) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const payload = {
        ...settings,
        room_map_by_room_id: parseJsonObject('Room map by roomId', roomMapByRoomIdText),
        room_map_by_unit_id: parseJsonObject('Room map by unitId', roomMapByUnitIdText),
        channel_map_by_source: parseJsonObject('Channel map by source', channelMapText),
        property_map_by_id: parseJsonObject('Property map', propertyMapText),
      };
      const res = await updateBeds24IntegrationSettings(payload);
      const nextSettings = { ...DEFAULT_SETTINGS, ...(res?.settings || payload) };
      setSettings(nextSettings);
      setRoomMapByRoomIdText(pretty(nextSettings.room_map_by_room_id));
      setRoomMapByUnitIdText(pretty(nextSettings.room_map_by_unit_id));
      setChannelMapText(pretty(nextSettings.channel_map_by_source));
      setPropertyMapText(pretty(nextSettings.property_map_by_id));
      setNotice(res?.message || 'Beds24 settings saved.');
    } catch (err) {
      setError(err.message || 'Failed to save Beds24 settings.');
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    if (!canSync) return;
    setTesting(true);
    setError('');
    setNotice('');
    setTestResult(null);
    try {
      const result = await testBeds24IntegrationConnection();
      setTestResult(result || null);
      setNotice('Beds24 connection test succeeded.');
    } catch (err) {
      setError(err.message || 'Beds24 connection test failed.');
    } finally {
      setTesting(false);
    }
  }

  async function runSyncBooking() {
    if (!canSync) return;
    const bookingId = String(syncBookingId || '').trim();
    if (!bookingId) {
      setError('Enter a Beds24 booking ID.');
      return;
    }
    setSyncing(true);
    setError('');
    setNotice('');
    try {
      const result = await syncBeds24Booking({
        booking_id: bookingId,
        include_invoice_items: !!recentSyncForm.include_invoice_items,
      });
      setNotice(`Booking synced: Beds24 ${result?.beds24_booking_id} -> ERP #${result?.local_booking_id}.`);
      setSyncBookingId('');
      if (canViewLogs) await refreshDebugData();
    } catch (err) {
      setError(err.message || 'Failed to sync booking.');
    } finally {
      setSyncing(false);
    }
  }

  async function runRebuildBookingMirror() {
    if (!canManage) return;
    const bookingId = String(syncBookingId || '').trim();
    if (!bookingId) {
      setError('Enter a Beds24 booking ID to rebuild.');
      return;
    }
    setRebuilding(true);
    setError('');
    setNotice('');
    try {
      const result = await rebuildBeds24BookingMirror({
        booking_id: bookingId,
        include_invoice_items: !!recentSyncForm.include_invoice_items,
      });
      const folioInfo = result?.folio_mirror
        ? ` Folio lines upserted: ${result.folio_mirror.upserted_lines || 0}, removed: ${result.folio_mirror.removed_lines || 0}.`
        : '';
      setNotice(`Mirror rebuilt: Beds24 ${result?.beds24_booking_id} -> ERP #${result?.local_booking_id}.${folioInfo}`);
      setSyncBookingId('');
      if (canViewLogs) await refreshDebugData();
    } catch (err) {
      setError(err.message || 'Failed to rebuild booking mirror.');
    } finally {
      setRebuilding(false);
    }
  }

  async function runSyncRecent() {
    if (!canSync) return;
    setSyncing(true);
    setError('');
    setNotice('');
    try {
      const payload = {
        limit: Number(recentSyncForm.limit || 25),
        status: recentSyncForm.status || null,
        filter: recentSyncForm.filter || null,
        include_invoice_items: !!recentSyncForm.include_invoice_items,
      };
      const result = await syncBeds24Recent(payload);
      setNotice(`Recent sync complete: ${result?.synced || 0} synced, ${result?.failed || 0} failed.`);
      if (canViewLogs) await refreshDebugData();
    } catch (err) {
      setError(err.message || 'Failed to run recent sync.');
    } finally {
      setSyncing(false);
    }
  }

  async function runBackfill() {
    if (!canSync) return;
    setBackfillRunning(true);
    setBackfillResult(null);
    setError('');
    setNotice('');
    try {
      const statuses = String(backfillForm.statuses || '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      const result = await syncBeds24Backfill({
        from_date: backfillForm.from_date,
        to_date: backfillForm.to_date,
        property_id: backfillForm.property_id || null,
        statuses,
        include_invoice_items: !!backfillForm.include_invoice_items,
        dry_run: !!backfillForm.dry_run,
        chunk_days: Number(backfillForm.chunk_days || 31),
        request_delay_seconds: Number(backfillForm.request_delay_seconds || 0),
      });
      setBackfillResult(result || null);
      const rateLimitText = result?.rate_limited
        ? ` Stopped at Beds24 rate limit${result?.retry_after_seconds ? `; retry in about ${result.retry_after_seconds} seconds` : ''}.`
        : '';
      setNotice(`${result?.dry_run ? 'Backfill preview' : 'Historical import'} ${result?.rate_limited ? 'paused' : 'complete'}: ${result?.fetched || 0} fetched, ${result?.created || 0} created, ${result?.updated || 0} updated, ${result?.skipped || 0} skipped, ${result?.failed || 0} failed.${rateLimitText}`);
      if (canViewLogs) await refreshDebugData();
    } catch (err) {
      setError(err.message || 'Failed to run historical import.');
    } finally {
      setBackfillRunning(false);
    }
  }

  async function runResetPreview() {
    if (!canManage) return;
    setPreviewLoading(true);
    setError('');
    setNotice('');
    try {
      const preview = await previewBeds24Reset({ mode: resetMode });
      setResetPreview(preview || null);
      setResetConfirmation('');
      setNotice('Reset preview loaded. Review counts before executing.');
    } catch (err) {
      setError(err.message || 'Failed to load reset preview.');
    } finally {
      setPreviewLoading(false);
    }
  }

  async function runResetExecute() {
    if (!canManage) return;
    if (!resetPreview?.required_confirmation) {
      setError('Load reset preview first.');
      return;
    }
    if (String(resetConfirmation || '').trim() !== String(resetPreview.required_confirmation || '').trim()) {
      setError(`Type exact confirmation phrase: ${resetPreview.required_confirmation}`);
      return;
    }
    setResetting(true);
    setError('');
    setNotice('');
    try {
      const result = await executeBeds24Reset({
        mode: resetMode,
        confirmation: resetConfirmation,
      });
      setNotice(`Reset executed (${result?.mode || resetMode}).`);
      setResetPreview(null);
      setResetConfirmation('');
      await load();
    } catch (err) {
      setError(err.message || 'Failed to execute reset.');
    } finally {
      setResetting(false);
    }
  }

  if (loading) {
    return (
      <section className="section">
        <h1>Beds24 Integration</h1>
        <p className="muted">Loading integration settings...</p>
      </section>
    );
  }

  return (
    <div className="stack">
      <section className="section">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1>Beds24 Integration</h1>
            <p className="muted">Beds24 is the booking source of truth. ERP mirrors bookings/guests for finance and reporting.</p>
          </div>
          <button type="button" onClick={saveSettings} disabled={!canManage || saving}>
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
        {!!notice && <p className="success-text">{notice}</p>}
        {!!error && <p className="error-text">{error}</p>}
      </section>

      <section className="section">
        <h2>Connection & Sync Mode</h2>
        <div className="form-grid">
          <label>
            Enabled
            <select value={String(!!settings.enabled)} onChange={(e) => patchSettings({ enabled: e.target.value === 'true' })}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </label>
          <label>
            API Base URL
            <input value={settings.api_base_url || ''} onChange={(e) => patchSettings({ api_base_url: e.target.value })} />
          </label>
          <label>
            Manual Sync Only
            <select value={String(!!settings.manual_sync_only)} onChange={(e) => patchSettings({ manual_sync_only: e.target.value === 'true' })}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Include Invoice Items on Fetch
            <select value={String(!!settings.include_invoice_items)} onChange={(e) => patchSettings({ include_invoice_items: e.target.value === 'true' })}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Access Token
            <input value={settings.access_token || ''} onChange={(e) => patchSettings({ access_token: e.target.value })} placeholder="Optional if refresh token is set" />
          </label>
          <label>
            Refresh Token
            <input value={settings.refresh_token || ''} onChange={(e) => patchSettings({ refresh_token: e.target.value })} placeholder="Recommended for API V2 token refresh" />
          </label>
          <label>
            Invite Code
            <input value={settings.invite_code || ''} onChange={(e) => patchSettings({ invite_code: e.target.value })} placeholder="Used once to exchange setup token" />
          </label>
          <label>
            Log Verbosity
            <select value={settings.log_verbosity || 'normal'} onChange={(e) => patchSettings({ log_verbosity: e.target.value })}>
              <option value="normal">Normal</option>
              <option value="verbose">Verbose</option>
            </select>
          </label>
        </div>
        <div className="row wrap">
          <button type="button" onClick={testConnection} disabled={!canSync || testing}>
            {testing ? 'Testing...' : 'Test Connection'}
          </button>
          {testResult && (
            <div className="muted">
              Connected at {testResult.checked_at || 'n/a'} · sample booking {testResult.sample_booking_id || 'none'}
            </div>
          )}
          <div className="muted">Last sync log: {lastLogTimestamp || 'none yet'}</div>
        </div>
      </section>

      <section className="section">
        <h2>Webhook</h2>
        <div className="form-grid">
          <label>
            Webhook Enabled
            <select value={String(!!settings.webhook_enabled)} onChange={(e) => patchSettings({ webhook_enabled: e.target.value === 'true' })}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </label>
          <label>
            Require Webhook Secret
            <select value={String(!!settings.webhook_require_secret)} onChange={(e) => patchSettings({ webhook_require_secret: e.target.value === 'true' })}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Webhook Secret
            <input value={settings.webhook_secret || ''} onChange={(e) => patchSettings({ webhook_secret: e.target.value })} />
          </label>
        </div>
        <p className="muted small">
          Webhook endpoint: <code>/api/integrations/beds24/webhook</code>. Deliveries are idempotent via booking upsert mapping.
        </p>
      </section>

      <section className="section">
        <h2>Mirroring Rules</h2>
        <div className="form-grid">
          <label>
            Auto-create Guest
            <select value={String(!!settings.auto_create_guest)} onChange={(e) => patchSettings({ auto_create_guest: e.target.value === 'true' })}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Auto-create Folio Mirror
            <select value={String(!!settings.auto_create_folio_mirror)} onChange={(e) => patchSettings({ auto_create_folio_mirror: e.target.value === 'true' })}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </label>
          <label>
            Auto-create Receivable Mirror
            <select value={String(!!settings.auto_create_receivable_mirror)} onChange={(e) => patchSettings({ auto_create_receivable_mirror: e.target.value === 'true' })}>
              <option value="false">No</option>
              <option value="true">Yes</option>
            </select>
          </label>
          <label>
            Auto-link Room
            <select value={String(!!settings.auto_link_room)} onChange={(e) => patchSettings({ auto_link_room: e.target.value === 'true' })}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Auto-link Channel
            <select value={String(!!settings.auto_link_channel)} onChange={(e) => patchSettings({ auto_link_channel: e.target.value === 'true' })}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Unknown Room Fallback
            <select value={settings.fallback_unknown_room_behavior || 'leave_unlinked'} onChange={(e) => patchSettings({ fallback_unknown_room_behavior: e.target.value })}>
              <option value="leave_unlinked">Leave Unlinked</option>
            </select>
          </label>
          <label>
            Unknown Channel Fallback
            <select value={settings.fallback_unknown_channel_behavior || 'leave_unlinked'} onChange={(e) => patchSettings({ fallback_unknown_channel_behavior: e.target.value })}>
              <option value="leave_unlinked">Leave Unlinked</option>
            </select>
          </label>
        </div>
      </section>

      <section className="section">
        <h2>Mappings</h2>
        <p className="muted">Set explicit mappings as JSON object pairs. Existing saved mappings are never changed unless you edit and save.</p>
        <p className="muted small">
          Room and channel mappings use local numeric IDs. Property mapping uses a local property reference string and is optional for single-property ERP setups.
        </p>
        <div className="form-grid">
          <label>
            roomId → local room_id
            <textarea rows={8} value={roomMapByRoomIdText} onChange={(e) => setRoomMapByRoomIdText(e.target.value)} />
          </label>
          <label>
            unitId → local room_id
            <textarea rows={8} value={roomMapByUnitIdText} onChange={(e) => setRoomMapByUnitIdText(e.target.value)} />
          </label>
          <label>
            source/originalOTA/referer → local channel_id
            <textarea rows={8} value={channelMapText} onChange={(e) => setChannelMapText(e.target.value)} />
          </label>
          <label>
            propertyId → local property reference (string, optional)
            <textarea rows={8} value={propertyMapText} onChange={(e) => setPropertyMapText(e.target.value)} />
          </label>
        </div>
        <p className="muted small">
          Example if not used: <code>{'{}'}</code>. Example if used: <code>{'{ "253718": "main-resort" }'}</code>.
        </p>
      </section>

      <section className="section">
        <h2>Local Mapping Helper IDs</h2>
        <p className="muted">Use these IDs when maintaining explicit mapping JSON. Existing mappings are preserved unless you edit and save them.</p>
        <div className="grid two">
          <div className="card">
            <h3>Rooms</h3>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Room No</th>
                    <th>Name</th>
                  </tr>
                </thead>
                <tbody>
                  {mappingHelpers.rooms.map((row) => (
                    <tr key={`room-${row.id}`}>
                      <td>{row.id}</td>
                      <td>{row.room_no || ''}</td>
                      <td>{row.name || ''}</td>
                    </tr>
                  ))}
                  {!mappingHelpers.rooms.length && (
                    <tr>
                      <td colSpan={3} className="muted">No local rooms found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <div className="card">
            <h3>Booking Channels</h3>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Code</th>
                    <th>Name</th>
                    <th>Prepaid</th>
                  </tr>
                </thead>
                <tbody>
                  {mappingHelpers.channels.map((row) => (
                    <tr key={`channel-${row.id}`}>
                      <td>{row.id}</td>
                      <td>{row.code || ''}</td>
                      <td>{row.name || ''}</td>
                      <td>{row.is_prepaid ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                  {!mappingHelpers.channels.length && (
                    <tr>
                      <td colSpan={4} className="muted">No booking channels found.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2>Manual Sync</h2>
        <div className="form-grid">
          <label>
            Sync One Booking (Beds24 ID)
            <input value={syncBookingId} onChange={(e) => setSyncBookingId(e.target.value)} placeholder="e.g. 1234567" />
          </label>
          <label>
            Recent Sync Limit
            <input type="number" min="1" max="200" value={recentSyncForm.limit} onChange={(e) => setRecentSyncForm((prev) => ({ ...prev, limit: Number(e.target.value || 25) }))} />
          </label>
          <label>
            Status Filter
            <input value={recentSyncForm.status} onChange={(e) => setRecentSyncForm((prev) => ({ ...prev, status: e.target.value }))} placeholder="new, confirmed, cancelled" />
          </label>
          <label>
            Filter
            <input value={recentSyncForm.filter} onChange={(e) => setRecentSyncForm((prev) => ({ ...prev, filter: e.target.value }))} placeholder="arrivals, departures, ... " />
          </label>
          <label>
            Include Invoice Items
            <select value={String(!!recentSyncForm.include_invoice_items)} onChange={(e) => setRecentSyncForm((prev) => ({ ...prev, include_invoice_items: e.target.value === 'true' }))}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
        </div>
        <div className="row wrap">
          <button type="button" onClick={runSyncBooking} disabled={!canSync || syncing}>
            {syncing ? 'Syncing...' : 'Sync Booking ID'}
          </button>
          <button type="button" className="secondary" onClick={runRebuildBookingMirror} disabled={!canManage || rebuilding}>
            {rebuilding ? 'Rebuilding...' : 'Rebuild One Booking Mirror'}
          </button>
          <button type="button" className="secondary" onClick={runSyncRecent} disabled={!canSync || syncing}>
            {syncing ? 'Syncing...' : 'Sync Recent Bookings'}
          </button>
        </div>
      </section>

      <section className="section">
        <h2>Backfill / Historical Import</h2>
        <div className="form-grid">
          <label>
            From Date
            <input type="date" value={backfillForm.from_date} onChange={(e) => setBackfillForm((prev) => ({ ...prev, from_date: e.target.value }))} />
          </label>
          <label>
            To Date
            <input type="date" value={backfillForm.to_date} onChange={(e) => setBackfillForm((prev) => ({ ...prev, to_date: e.target.value }))} />
          </label>
          <label>
            Property ID Filter
            <input value={backfillForm.property_id} onChange={(e) => setBackfillForm((prev) => ({ ...prev, property_id: e.target.value }))} placeholder="Optional Beds24 propertyId" />
          </label>
          <label>
            Statuses to Include
            <input value={backfillForm.statuses} onChange={(e) => setBackfillForm((prev) => ({ ...prev, statuses: e.target.value }))} placeholder="Optional: new, confirmed, cancelled" />
          </label>
          <label>
            Include Invoice Items
            <select value={String(!!backfillForm.include_invoice_items)} onChange={(e) => setBackfillForm((prev) => ({ ...prev, include_invoice_items: e.target.value === 'true' }))}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Dry Run / Preview Only
            <select value={String(!!backfillForm.dry_run)} onChange={(e) => setBackfillForm((prev) => ({ ...prev, dry_run: e.target.value === 'true' }))}>
              <option value="true">Yes</option>
              <option value="false">No, import now</option>
            </select>
          </label>
          <label>
            Chunk Size (days)
            <input type="number" min="1" max="92" value={backfillForm.chunk_days} onChange={(e) => setBackfillForm((prev) => ({ ...prev, chunk_days: Number(e.target.value || 31) }))} />
          </label>
          <label>
            API Delay (seconds)
            <input type="number" min="0" max="30" step="0.5" value={backfillForm.request_delay_seconds} onChange={(e) => setBackfillForm((prev) => ({ ...prev, request_delay_seconds: Number(e.target.value || 0) }))} />
          </label>
        </div>
        <div className="row wrap">
          <button type="button" onClick={runBackfill} disabled={!canSync || backfillRunning}>
            {backfillRunning ? 'Running Import...' : (backfillForm.dry_run ? 'Preview Backfill' : 'Run Historical Import')}
          </button>
          <span className="muted small">
            Date ranges are fetched in chunks and paged internally. The delay keeps requests within Beds24 API credit limits; re-runs update existing bookings.
          </span>
        </div>
        {!!backfillResult && (
          <div className="stack" style={{ marginTop: 12 }}>
            <div className="table-wrap">
              <table className="table dense-table">
                <tbody>
                  <tr><th>Mode</th><td>{backfillResult.dry_run ? 'Preview only' : 'Imported'}</td></tr>
                  {backfillResult.rate_limited && <tr><th>Rate Limit</th><td>Stopped by Beds24 credit limit{backfillResult.retry_after_seconds ? ` · retry in about ${backfillResult.retry_after_seconds} seconds` : ''}</td></tr>}
                  <tr><th>Range</th><td>{backfillResult.from_date} to {backfillResult.to_date}</td></tr>
                  <tr><th>Fetched</th><td>{backfillResult.fetched || 0}</td></tr>
                  <tr><th>Created</th><td>{backfillResult.created || 0}</td></tr>
                  <tr><th>Updated</th><td>{backfillResult.updated || 0}</td></tr>
                  <tr><th>Skipped</th><td>{backfillResult.skipped || 0}</td></tr>
                  <tr><th>Failed</th><td>{backfillResult.failed || 0}</td></tr>
                </tbody>
              </table>
            </div>
            {Array.isArray(backfillResult.errors) && backfillResult.errors.length > 0 && (
              <div className="ops-alert-list">
                <h3>Import Errors</h3>
                {backfillResult.errors.slice(0, 10).map((row, idx) => (
                  <p key={`backfill-error-${idx}`} className="error-text">{row.beds24_booking_id || row.range || 'chunk'}: {row.error || 'Unknown error'}</p>
                ))}
              </div>
            )}
            {Array.isArray(backfillResult.chunk_summaries) && backfillResult.chunk_summaries.length > 0 && (
              <details className="quiet-details">
                <summary>Chunk summary</summary>
                <div className="table-wrap">
                  <table className="table dense-table">
                    <thead><tr><th>Range</th><th>Status</th><th>Fetched</th><th>Created</th><th>Updated</th><th>Skipped</th><th>Failed</th></tr></thead>
                    <tbody>
                      {backfillResult.chunk_summaries.map((row, idx) => (
                        <tr key={`chunk-${idx}`}>
                          <td>{row.from_date} to {row.to_date}</td>
                          <td>{row.status || 'all'}</td>
                          <td>{row.fetched || 0}</td>
                          <td>{row.created || 0}</td>
                          <td>{row.updated || 0}</td>
                          <td>{row.skipped || 0}</td>
                          <td>{row.failed || 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        )}
      </section>

      {canManage && (
        <section className="section">
          <h2>Reset Tools (Admin)</h2>
          <p className="muted">
            Destructive actions require preview + explicit confirmation. Room/channel/property mappings are preserved.
          </p>
          <div className="form-grid">
            <label>
              Reset Mode
              <select value={resetMode} onChange={(e) => {
                setResetMode(e.target.value);
                setResetPreview(null);
                setResetConfirmation('');
              }}>
                {RESET_MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <label>
              Confirmation Phrase
              <input
                value={resetConfirmation}
                onChange={(e) => setResetConfirmation(e.target.value)}
                placeholder={resetPreview?.required_confirmation || 'Load preview first'}
              />
            </label>
          </div>
          <div className="row wrap">
            <button type="button" className="secondary" onClick={runResetPreview} disabled={previewLoading || resetting}>
              {previewLoading ? 'Loading Preview...' : 'Preview Reset Impact'}
            </button>
            <button type="button" onClick={runResetExecute} disabled={resetting || !resetPreview}>
              {resetting ? 'Executing Reset...' : 'Execute Reset'}
            </button>
          </div>
          {!!resetPreview && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(resetPreview.counts || {}).map(([key, value]) => (
                    <tr key={key}>
                      <td>{key}</td>
                      <td>{value}</td>
                    </tr>
                  ))}
                  {!Object.keys(resetPreview.counts || {}).length && (
                    <tr>
                      <td colSpan={2} className="muted">No records would be changed for this mode.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
          {!!resetPreview?.required_confirmation && (
            <p className="small muted">
              Required phrase: <code>{resetPreview.required_confirmation}</code>
            </p>
          )}
          {Array.isArray(resetPreview?.notes) && resetPreview.notes.length > 0 && (
            <div className="stack">
              {resetPreview.notes.map((note, idx) => (
                <p key={`reset-note-${idx}`} className="small muted">{note}</p>
              ))}
            </div>
          )}
        </section>
      )}

      {canViewLogs && (
        <section className="section">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Recent Sync Logs</h2>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setError('');
                Promise.all([fetchBeds24SyncLogs({ limit: 100 }), fetchBeds24SyncState({ limit: 100 })])
                  .then(([rows, stateRows]) => {
                    setLogs(Array.isArray(rows) ? rows : []);
                    setSyncStateRows(Array.isArray(stateRows) ? stateRows : []);
                  })
                  .catch((err) => setError(err.message || 'Failed to refresh logs.'));
              }}
            >
              Refresh Logs
            </button>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Source</th>
                  <th>Event</th>
                  <th>Status</th>
                  <th>Beds24 Booking</th>
                  <th>ERP Booking</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((row) => (
                  <tr key={row.id}>
                    <td>{row.created_at || ''}</td>
                    <td>{row.source_type || ''}</td>
                    <td>{row.event_type || ''}</td>
                    <td><span className={syncStatusClass(row.status)}>{row.status || ''}</span></td>
                    <td>{row.beds24_booking_id || ''}</td>
                    <td>{row.local_booking_id || ''}</td>
                    <td>{row.message || ''}</td>
                  </tr>
                ))}
                {!logs.length && (
                  <tr>
                    <td colSpan={7} className="muted">No sync logs yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {canViewLogs && (
        <section className="section">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h2>Recent Sync Mapping State</h2>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setError('');
                fetchBeds24SyncState({ limit: 100 })
                  .then((rows) => setSyncStateRows(Array.isArray(rows) ? rows : []))
                  .catch((err) => setError(err.message || 'Failed to refresh mapping state.'));
              }}
            >
              Refresh State
            </button>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Beds24 Booking</th>
                  <th>Property</th>
                  <th>roomId</th>
                  <th>unitId</th>
                  <th>referer</th>
                  <th>channel</th>
                  <th>apiSource</th>
                  <th>ERP Booking</th>
                  <th>ERP Guest</th>
                  <th>ERP Room</th>
                  <th>ERP Channel</th>
                  <th>Status</th>
                  <th>Warnings</th>
                </tr>
              </thead>
              <tbody>
                {syncStateRows.map((row) => (
                  <tr key={`sync-state-${row.beds24_booking_id}-${row.local_booking_id || 'none'}`}>
                    <td>{row.beds24_booking_id || ''}</td>
                    <td>{row.beds24_property_id || ''}</td>
                    <td>{row.beds24_room_id || ''}</td>
                    <td>{row.beds24_unit_id || ''}</td>
                    <td>{row.beds24_referer || ''}</td>
                    <td>{row.beds24_channel || ''}</td>
                    <td>{row.beds24_api_source || ''}</td>
                    <td>{row.local_booking_id || ''}</td>
                    <td>{row.local_guest_id || ''}</td>
                    <td>{row.local_room_id || ''}</td>
                    <td>{row.local_channel_id || ''}</td>
                    <td><span className={syncStatusClass(row.sync_status)}>{row.sync_status || ''}</span></td>
                    <td>{row.warning_text || ''}</td>
                  </tr>
                ))}
                {!syncStateRows.length && (
                  <tr>
                    <td colSpan={13} className="muted">No mapping state rows yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
