const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';
const CSRF_COOKIE_NAME = 'erp_csrf';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const CSRF_EXEMPT_PATHS = new Set(['/auth/login', '/auth/integration/token', '/auth/csrf']);
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function getToken() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('erp_token') || '';
}

function setToken(token) {
  if (typeof window !== 'undefined') localStorage.setItem('erp_token', token);
}

function clearToken() {
  if (typeof window !== 'undefined') localStorage.removeItem('erp_token');
}

function getCookie(name) {
  if (typeof document === 'undefined') return '';
  const prefix = `${encodeURIComponent(name)}=`;
  const row = document.cookie.split('; ').find((entry) => entry.startsWith(prefix));
  if (!row) return '';
  return decodeURIComponent(row.slice(prefix.length));
}

async function ensureCsrfHeader(path, method, headers) {
  const normalizedMethod = String(method || 'GET').toUpperCase();
  if (!UNSAFE_METHODS.has(normalizedMethod) || CSRF_EXEMPT_PATHS.has(path)) return;
  let csrfToken = getCookie(CSRF_COOKIE_NAME);
  if (!csrfToken) {
    try {
      const res = await fetch(`${API_BASE}/auth/csrf`, { cache: 'no-store', credentials: 'include' });
      if (res.ok) {
        const data = await res.json().catch(() => null);
        csrfToken = data?.csrf_token || getCookie(CSRF_COOKIE_NAME);
      }
    } catch {
      csrfToken = getCookie(CSRF_COOKIE_NAME);
    }
  }
  if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken;
}

async function request(path, init = {}) {
  const headers = { ...(init.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!(init.body instanceof FormData) && init.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  await ensureCsrfHeader(path, init.method, headers);
  const res = await fetch(`${API_BASE}${path}`, { cache: 'no-store', credentials: 'include', ...init, headers });
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) throw new Error(readApiMessage(data?.detail || data?.message || data?.error || data) || 'Request failed');
  return data;
}

function readApiMessage(value) {
  if (!value) return '';
  if (typeof value === 'string') return value;
  if (value instanceof Error) return value.message || '';
  if (typeof value === 'object') {
    const direct = value.message || value.detail || value.error || value.msg;
    if (typeof direct === 'string' && direct.trim()) return direct;
    try { return JSON.stringify(value, null, 2); } catch { return 'Request failed with an unreadable response.'; }
  }
  return String(value);
}

export { API_BASE, getToken, setToken, clearToken, request, readApiMessage };

export const bootstrap = () => request('/auth/bootstrap', { method: 'POST' });
export const login = (payload) => request('/auth/login', { method: 'POST', body: JSON.stringify(payload) });
export const logout = () => request('/auth/logout', { method: 'POST' });
export const me = () => request('/auth/me');

export const getDashboard = () => request('/dashboard/summary');
export const globalSearch = (q, limit = 8) => request(`/search/?q=${encodeURIComponent(q || '')}&limit=${encodeURIComponent(limit)}`);
export const getSystemSettings = () => request('/system-settings');
export const updateSystemSettings = (payload) => request('/system-settings', { method: 'PUT', body: JSON.stringify(payload) });
export const fetchNextCodePreview = (entity, draft = '') => request(`/system-settings/next-code?entity=${encodeURIComponent(entity)}${draft ? `&draft=${encodeURIComponent(draft)}` : ''}`);
export const saveDashboardUserOverride = (payload) => request('/system-settings/dashboard/user-override', { method: 'POST', body: JSON.stringify(payload) });
export const fetchBeds24IntegrationSettings = () => request('/integrations/beds24/settings');
export const updateBeds24IntegrationSettings = (payload) => request('/integrations/beds24/settings', { method: 'PUT', body: JSON.stringify(payload) });
export const testBeds24IntegrationConnection = () => request('/integrations/beds24/test-connection', { method: 'POST' });
export const syncBeds24Booking = (payload) => request('/integrations/beds24/sync/booking', { method: 'POST', body: JSON.stringify(payload) });
export const rebuildBeds24BookingMirror = (payload) => request('/integrations/beds24/sync/booking/rebuild', { method: 'POST', body: JSON.stringify(payload) });
export const syncBeds24Recent = (payload) => request('/integrations/beds24/sync/recent', { method: 'POST', body: JSON.stringify(payload) });
export const syncBeds24Backfill = (payload) => request('/integrations/beds24/sync/backfill', { method: 'POST', body: JSON.stringify(payload) });
export const reclassifyBeds24FolioLines = (payload) => request('/integrations/beds24/folio-lines/reclassify', { method: 'POST', body: JSON.stringify(payload) });
export const fetchBeds24SyncLogs = (params = {}) => request(`/integrations/beds24/logs${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const fetchBeds24SyncState = (params = {}) => request(`/integrations/beds24/sync-state${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const fetchBeds24MappingHelpers = () => request('/integrations/beds24/mapping-helpers');
export const previewBeds24Reset = (payload) => request('/integrations/beds24/reset/preview', { method: 'POST', body: JSON.stringify(payload) });
export const executeBeds24Reset = (payload) => request('/integrations/beds24/reset/execute', { method: 'POST', body: JSON.stringify(payload) });
export const fetchPayrollIntegrationReceipts = (status = '') => request(`/integrations/payroll/receipts${status ? `?status=${encodeURIComponent(status)}` : ''}`);
export const fetchPayrollIntegrationReceipt = (id) => request(`/integrations/payroll/receipts/${id}`);
export const approvePayrollIntegrationReceipt = (id) => request(`/integrations/payroll/receipts/${id}/approve`, { method: 'POST' });
export const rejectPayrollIntegrationReceipt = (id, reason) => request(`/integrations/payroll/receipts/${id}/reject?reason=${encodeURIComponent(reason)}`, { method: 'POST' });
export const postPayrollIntegrationReceipt = (id) => request(`/integrations/payroll/receipts/${id}/post?confirm=true`, { method: 'POST' });

export const fetchTaxonomy = () => request('/taxonomy/');
export const fetchModuleTaxonomy = (slug) => request(`/taxonomy/${slug}`);
export const fetchTaxonomyNodes = () => request('/taxonomy/nodes');
export const createTaxonomyNode = (payload) => request('/taxonomy/nodes', { method:'POST', body: JSON.stringify(payload) });
export const updateTaxonomyNode = (id,payload) => request(`/taxonomy/nodes/${id}`, { method:'PUT', body: JSON.stringify(payload) });
export const deleteTaxonomyNode = (id) => request(`/taxonomy/nodes/${id}`, { method:'DELETE' });

export const getModuleRecords = (slug, search='') => request(`/records/${slug}/records${search ? `?search=${encodeURIComponent(search)}` : ''}`);
export const createRecord = (slug, payload) => request(`/records/${slug}/records`, { method:'POST', body: JSON.stringify(payload)});
export const updateRecord = (id, payload) => request(`/records/single/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deleteRecord = (id) => request(`/records/single/${id}`, { method:'DELETE' });
export const approveRecord = (id, approved=true, { note = '' } = {}) => request(`/records/single/${id}/approve`, { method:'POST', body: JSON.stringify({ approved, note: note || null }) });

export const fetchEmployees = () => request('/people/employees');
export const createEmployee = (payload) => request('/people/employees', { method:'POST', body: JSON.stringify(payload)});
export const updateEmployee = (id,payload) => request(`/people/employees/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deleteEmployee = (id) => request(`/people/employees/${id}`, { method:'DELETE' });
export const fetchAttendance = (params = {}) => request(`/people/attendance${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const createAttendance = (payload) => request('/people/attendance', { method:'POST', body: JSON.stringify(payload)});
export const updateAttendance = (id, payload) => request(`/people/attendance/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const bulkCreateAttendance = (entries) => request('/people/attendance/bulk', { method:'POST', body: JSON.stringify({ entries })});
export const importAttendance = (entries) => request('/people/attendance/import', { method:'POST', body: JSON.stringify({ entries })});
export const deleteAttendance = (id) => request(`/people/attendance/${id}`, { method:'DELETE' });

export const fetchInventoryItems = () => request('/stock/items');
export const createInventoryItem = (payload) => request('/stock/items', { method:'POST', body: JSON.stringify(payload)});
export const updateInventoryItem = (id,payload) => request(`/stock/items/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deleteInventoryItem = (id) => request(`/stock/items/${id}`, { method:'DELETE' });
export const fetchStockMovements = () => request('/stock/movements');
export const createStockMovement = (payload) => request('/stock/movements', { method:'POST', body: JSON.stringify(payload)});
export const fetchBatches = () => request('/stock/batches');
export const fetchAllocations = (movementId) => request(`/stock/allocations/${movementId}`);

export const fetchAssets = () => request('/asset-registry/assets');
export const createAsset = (payload) => request('/asset-registry/assets', { method:'POST', body: JSON.stringify(payload)});
export const updateAsset = (id, payload) => request(`/asset-registry/assets/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const fetchDepreciationLogs = (assetId='') => request(`/asset-registry/depreciation-logs${assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''}`);
export const depreciateAsset = (assetId, payload) => request(`/asset-registry/assets/${assetId}/depreciate`, { method:'POST', body: JSON.stringify(payload)});
export const depreciateAssetsBatch = (payload) => request('/asset-registry/assets/depreciate-batch', { method:'POST', body: JSON.stringify(payload)});
export const fetchMaintenanceLogs = (assetId='') => request(`/asset-registry/maintenance-logs${assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''}`);
export const createAssetMaintenance = (assetId, payload) => request(`/asset-registry/assets/${assetId}/maintenance`, { method:'POST', body: JSON.stringify(payload)});
export const fetchDisposalLogs = (assetId='') => request(`/asset-registry/disposal-logs${assetId ? `?asset_id=${encodeURIComponent(assetId)}` : ''}`);
export const disposeAsset = (assetId, payload) => request(`/asset-registry/assets/${assetId}/dispose`, { method:'POST', body: JSON.stringify(payload)});

export const fetchBookings = () => request('/reservations/bookings');
export const fetchBooking = (id) => request(`/reservations/bookings/${id}`);
export const fetchBookingCalendar = (params = {}) => request(`/reservations/bookings/calendar${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const reclassifyBookingFolioLines = (id, payload) => request(`/reservations/bookings/${id}/folio-lines/reclassify`, { method: 'POST', body: JSON.stringify(payload) });
export const createBooking = (payload) => request('/reservations/bookings', { method:'POST', body: JSON.stringify(payload)});
export const updateBooking = (id, payload) => request(`/reservations/bookings/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const fetchBreakfastLogs = () => request('/reservations/breakfast-logs');
export const createBreakfastLog = (payload) => request('/reservations/breakfast-logs', { method:'POST', body: JSON.stringify(payload)});
export const fetchPayouts = () => request('/channel/payouts');
export const fetchPayoutChannelOptions = () => request('/channel/payout-channel-options');
export const createPayout = (payload) => request('/channel/payouts', { method:'POST', body: JSON.stringify(payload)});
export const updatePayout = (id, payload) => request(`/channel/payouts/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const settlePayout = (id, payload) => request(`/channel/payouts/${id}/settle`, { method:'POST', body: JSON.stringify(payload)});

export const fetchPayrollRuns = () => request('/payroll/runs');
export const createPayrollRun = (payload) => request('/payroll/runs', { method:'POST', body: JSON.stringify(payload)});
export const generatePayrollRun = (payload) => request('/payroll/runs/generate', { method:'POST', body: JSON.stringify(payload)});
export const postPayrollRun = (id) => request(`/payroll/runs/${id}/post`, { method:'POST' });
export const approvePayrollRun = (id) => request(`/approvals/payroll/${id}/approve`, { method:'POST' });

export const fetchJournalEntries = () => request('/journals/entries');
export const createJournalEntry = (payload) => request('/journals/entries', { method:'POST', body: JSON.stringify(payload)});
export const fetchTrialBalance = () => request('/journals/trial-balance');
export const lockJournalEntry = (id) => request(`/approvals/journals/${id}/lock`, { method:'POST' });

export const fetchMasterValues = (group = '', activeOnly = true) => {
  const params = [];
  if (group) params.push(`group_name=${encodeURIComponent(group)}`);
  if (activeOnly === false) params.push('active_only=false');
  return request(`/master/values${params.length ? `?${params.join('&')}` : ''}`);
};
export const createMasterValue = (payload) => request('/master/values', { method:'POST', body: JSON.stringify(payload)});
export const updateMasterValue = (id,payload) => request(`/master/values/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deleteMasterValue = (id) => request(`/master/values/${id}`, { method:'DELETE' });

export const seedDemo = () => request('/seed/demo', { method:'POST' });

export const fetchMenuItems = () => request('/menu/items');
export const createMenuItem = (payload) => request('/menu/items', { method:'POST', body: JSON.stringify(payload)});
export const updateMenuItem = (id,payload) => request(`/menu/items/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deleteMenuItem = (id) => request(`/menu/items/${id}`, { method:'DELETE' });
export const fetchRecipe = (id) => request(`/menu/items/${id}/recipe`);
export const createRecipeLine = (id,payload) => request(`/menu/items/${id}/recipe`, { method:'POST', body: JSON.stringify(payload)});
export const deleteRecipeLine = (id) => request(`/menu/recipe/${id}`, { method:'DELETE' });
export const fetchPrepComponents = () => request('/menu/components');
export const createPrepComponent = (payload) => request('/menu/components', { method:'POST', body: JSON.stringify(payload)});
export const updatePrepComponent = (id,payload) => request(`/menu/components/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deletePrepComponent = (id) => request(`/menu/components/${id}`, { method:'DELETE' });
export const getPrepComponentCosting = (id) => request(`/menu/components/${id}/costing`);
export const fetchMenuSkus = (menuItemId=null) => request(`/menu/skus${menuItemId ? `?menu_item_id=${encodeURIComponent(menuItemId)}` : ''}`);
export const fetchItemSkus = (itemId) => request(`/menu/items/${itemId}/skus`);
export const createMenuSku = (payload) => request('/menu/skus', { method:'POST', body: JSON.stringify(payload)});
export const updateMenuSku = (id,payload) => request(`/menu/skus/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deleteMenuSku = (id) => request(`/menu/skus/${id}`, { method:'DELETE' });
export const getMenuSkuCosting = (id) => request(`/menu/skus/${id}/costing`);
export const fetchMenuPromotions = () => request('/menu/promotions');
export const createMenuPromotion = (payload) => request('/menu/promotions', { method:'POST', body: JSON.stringify(payload)});
export const updateMenuPromotion = (id,payload) => request(`/menu/promotions/${id}`, { method:'PUT', body: JSON.stringify(payload)});
export const deleteMenuPromotion = (id) => request(`/menu/promotions/${id}`, { method:'DELETE' });
export const fetchSaleOrders = (limit=100) => request(`/menu/sales?limit=${encodeURIComponent(limit)}`);
export const fetchSaleOrder = (id) => request(`/menu/sales/${id}`);
export const createSaleOrder = (payload) => request('/menu/sales', { method:'POST', body: JSON.stringify(payload)});
export const voidSaleOrder = (id, payload) => request(`/menu/sales/${id}/void`, { method:'POST', body: JSON.stringify(payload)});
export const fetchStaffMeals = () => request('/menu/staff-meals');
export const createStaffMeal = (payload) => request('/menu/staff-meals', { method:'POST', body: JSON.stringify(payload)});

export const fetchBirBooks = (periodKey='') => request(`/bir/books${periodKey ? `?period_key=${encodeURIComponent(periodKey)}` : ''}`);
export const generateBirBooks = (payload) => request('/bir/generate', { method:'POST', body: JSON.stringify(payload)});
export const fetchBirCandidates = (periodKey) => request(`/bir/candidates?period_key=${encodeURIComponent(periodKey)}`);
export const saveBirSelections = (payload) => request('/bir/selections', { method:'POST', body: JSON.stringify(payload)});
export const fetchLocks = () => request('/bir/locks');
export const saveLock = (payload) => request('/bir/locks', { method:'POST', body: JSON.stringify(payload)});

export const fetchUsers = () => request('/auth/users');
export const createUser = (payload) => request('/auth/users', { method:'POST', body: JSON.stringify(payload)});
export const updateUser = (id,payload) => request(`/auth/users/${id}`, { method:'PUT', body: JSON.stringify(payload)});

export const fetchManagementReport = ({ startDate = '', endDate = '' } = {}) => request(`/reports/management${(startDate || endDate) ? `?${startDate ? `start_date=${encodeURIComponent(startDate)}` : ''}${startDate && endDate ? '&' : ''}${endDate ? `end_date=${encodeURIComponent(endDate)}` : ''}` : ''}`);
export const fetchFinancialStatements = ({ startDate = '', endDate = '', asOfDate = '' } = {}) => {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  if (asOfDate) params.set('as_of_date', asOfDate);
  const query = params.toString();
  return request(`/reports/financial-statements${query ? `?${query}` : ''}`);
};
export const fetchAgingReport = (asOfDate = '') => request(`/reports/ar-ap-aging${asOfDate ? `?as_of_date=${encodeURIComponent(asOfDate)}` : ''}`);
export const fetchSettlements = ({ recordId = null, limit = 200 } = {}) => request(`/reports/settlements?limit=${encodeURIComponent(limit)}${recordId ? `&record_id=${encodeURIComponent(recordId)}` : ''}`);
export const createSettlement = (payload) => request('/reports/settlements', { method: 'POST', body: JSON.stringify(payload) });

export const fetchEvents = (params = {}) => request(`/events/${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const createEvent = (payload) => request('/events/', { method: 'POST', body: JSON.stringify(payload) });
export const updateEvent = (id, payload) => request(`/events/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const confirmEvent = (id, payload = {}) => request(`/events/${id}/confirm`, { method: 'POST', body: JSON.stringify(payload) });
export const completeEvent = (id, payload = {}) => request(`/events/${id}/complete`, { method: 'POST', body: JSON.stringify(payload) });
export const cancelEvent = (id, payload = {}) => request(`/events/${id}/cancel`, { method: 'POST', body: JSON.stringify(payload) });
export const recordEventPayment = (id, payload) => request(`/events/${id}/payments`, { method: 'POST', body: JSON.stringify(payload) });

export async function fetchManagementCsv({ startDate = '', endDate = '' } = {}) {
  const token = getToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const query = `${startDate || endDate ? '?' : ''}${startDate ? `start_date=${encodeURIComponent(startDate)}` : ''}${startDate && endDate ? '&' : ''}${endDate ? `end_date=${encodeURIComponent(endDate)}` : ''}`;
  const res = await fetch(`${API_BASE}/reports/management.csv${query}`, { cache: 'no-store', credentials: 'include', headers });
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    throw new Error(readApiMessage(data?.detail || data?.message || data?.error || data) || 'Failed to export management CSV');
  }
  return await res.text();
}

export async function downloadSetupImportTemplate(scope = 'all') {
  const token = getToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/setup-imports/template?scope=${encodeURIComponent(scope)}`, { cache: 'no-store', credentials: 'include', headers });
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    throw new Error(readApiMessage(data?.detail || data?.message || data?.error || data) || 'Failed to download setup template');
  }
  return await res.blob();
}

export function importSetupWorkbook({ file, dryRun = true, replaceRecipeLines = true }) {
  const form = new FormData();
  form.append('file', file);
  form.append('dry_run', String(!!dryRun));
  form.append('replace_recipe_lines', String(!!replaceRecipeLines));
  return request('/setup-imports/import', { method: 'POST', body: form });
}

export const fetchAttachments = ({ entityType = '', entityId = null, limit = 200 } = {}) => request(`/attachments/?limit=${encodeURIComponent(limit)}${entityType ? `&entity_type=${encodeURIComponent(entityType)}` : ''}${entityId ? `&entity_id=${encodeURIComponent(entityId)}` : ''}`);
export const deleteAttachment = (id) => request(`/attachments/${id}`, { method: 'DELETE' });

function readFilenameFromDisposition(value) {
  if (!value) return '';
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1].trim().replace(/^"|"$/g, ''));
  const plainMatch = value.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ? plainMatch[1].trim() : '';
}

export async function downloadAttachment(id) {
  const token = getToken();
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/attachments/${encodeURIComponent(id)}/download`, { cache: 'no-store', credentials: 'include', headers });
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    throw new Error(readApiMessage(data?.detail || data?.message || data?.error || data) || 'Failed to download attachment');
  }
  return {
    blob: await res.blob(),
    filename: readFilenameFromDisposition(res.headers.get('content-disposition')),
  };
}

export async function uploadAttachment({ file, entityType, entityId, note = '' }) {
  const form = new FormData();
  form.append('file', file);
  form.append('entity_type', entityType);
  form.append('entity_id', String(entityId));
  if (note) form.append('note', note);
  return request('/attachments/upload', { method: 'POST', body: form });
}

// Guests + Folios
export const fetchGuests = (params = {}) => request(`/guests${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const searchGuests = (q, limit = 30) => request(`/guests/search?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`);
export const fetchGuest = (id) => request(`/guests/${id}`);
export const fetchGuestHistory = (id) => request(`/guests/${id}/history`);
export const createGuest = (payload) => request('/guests', { method: 'POST', body: JSON.stringify(payload) });
export const updateGuest = (id, payload) => request(`/guests/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const mergeGuests = (payload) => request('/guests/merge', { method: 'POST', body: JSON.stringify(payload) });

export const fetchRoomFolios = (params = {}) => request(`/room-folios${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const fetchRoomFolio = (id) => request(`/room-folios/${id}`);
export const createRoomFolio = (payload) => request('/room-folios', { method: 'POST', body: JSON.stringify(payload) });
export const updateRoomFolio = (id, payload) => request(`/room-folios/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const updateRoomFolioStatus = (id, payload) => request(`/room-folios/${id}/status`, { method: 'POST', body: JSON.stringify(payload) });
export const createRoomFolioLine = (folioId, payload) => request(`/room-folios/${folioId}/lines`, { method: 'POST', body: JSON.stringify(payload) });
export const updateRoomFolioLine = (lineId, payload) => request(`/room-folios/lines/${lineId}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteRoomFolioLine = (lineId) => request(`/room-folios/lines/${lineId}`, { method: 'DELETE' });
export const reverseRoomFolioLine = (lineId, payload) => request(`/room-folios/lines/${lineId}/reverse`, { method: 'POST', body: JSON.stringify(payload) });
export const transferRoomFolioLine = (lineId, payload) => request(`/room-folios/lines/${lineId}/transfer`, { method: 'POST', body: JSON.stringify(payload) });
export const settleRoomFolio = (folioId, payload = {}) => request(`/room-folios/${folioId}/settle`, { method: 'POST', body: JSON.stringify(payload) });

// Rooms setup entities
export const fetchRoomTypes = (activeOnly = false) => request(`/room-types?active_only=${String(!!activeOnly)}`);
export const createRoomType = (payload) => request('/room-types', { method: 'POST', body: JSON.stringify(payload) });
export const updateRoomType = (id, payload) => request(`/room-types/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteRoomType = (id) => request(`/room-types/${id}`, { method: 'DELETE' });

export const fetchRoomsEntity = (activeOnly = false) => request(`/rooms?active_only=${String(!!activeOnly)}`);
export const createRoomEntity = (payload) => request('/rooms', { method: 'POST', body: JSON.stringify(payload) });
export const updateRoomEntity = (id, payload) => request(`/rooms/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteRoomEntity = (id) => request(`/rooms/${id}`, { method: 'DELETE' });

export const fetchRatePlansEntity = (activeOnly = false) => request(`/rate-plans?active_only=${String(!!activeOnly)}`);
export const createRatePlanEntity = (payload) => request('/rate-plans', { method: 'POST', body: JSON.stringify(payload) });
export const updateRatePlanEntity = (id, payload) => request(`/rate-plans/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteRatePlanEntity = (id) => request(`/rate-plans/${id}`, { method: 'DELETE' });

export const fetchBookingChannels = (activeOnly = false) => request(`/booking-channels?active_only=${String(!!activeOnly)}`);
export const createBookingChannel = (payload) => request('/booking-channels', { method: 'POST', body: JSON.stringify(payload) });
export const updateBookingChannel = (id, payload) => request(`/booking-channels/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteBookingChannel = (id) => request(`/booking-channels/${id}`, { method: 'DELETE' });

export const fetchRoomPackageRules = (activeOnly = false) => request(`/room-package-rules?active_only=${String(!!activeOnly)}`);
export const createRoomPackageRule = (payload) => request('/room-package-rules', { method: 'POST', body: JSON.stringify(payload) });
export const updateRoomPackageRule = (id, payload) => request(`/room-package-rules/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteRoomPackageRule = (id) => request(`/room-package-rules/${id}`, { method: 'DELETE' });

// Suppliers + procurement workflows
export const fetchSuppliersEntity = (params = {}) => request(`/suppliers${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const createSupplierEntity = (payload) => request('/suppliers', { method: 'POST', body: JSON.stringify(payload) });
export const updateSupplierEntity = (id, payload) => request(`/suppliers/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteSupplierEntity = (id) => request(`/suppliers/${id}`, { method: 'DELETE' });

export const fetchPurchaseRequests = (params = {}) => request(`/purchase-requests${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const createPurchaseRequest = (payload) => request('/purchase-requests', { method: 'POST', body: JSON.stringify(payload) });
export const updatePurchaseRequest = (id, payload) => request(`/purchase-requests/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const updatePurchaseRequestStatus = (id, payload) => request(`/purchase-requests/${id}/status`, { method: 'POST', body: JSON.stringify(payload) });
export const convertPurchaseRequestToPo = (id) => request(`/purchase-requests/${id}/convert-to-po`, { method: 'POST' });
export const deletePurchaseRequest = (id) => request(`/purchase-requests/${id}`, { method: 'DELETE' });

export const fetchPurchaseOrders = (params = {}) => request(`/purchase-orders${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const createPurchaseOrder = (payload) => request('/purchase-orders', { method: 'POST', body: JSON.stringify(payload) });
export const updatePurchaseOrder = (id, payload) => request(`/purchase-orders/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const updatePurchaseOrderStatus = (id, payload) => request(`/purchase-orders/${id}/status`, { method: 'POST', body: JSON.stringify(payload) });
export const deletePurchaseOrder = (id) => request(`/purchase-orders/${id}`, { method: 'DELETE' });

export const fetchReceivingRecords = (params = {}) => request(`/receiving${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const createReceivingRecord = (payload) => request('/receiving', { method: 'POST', body: JSON.stringify(payload) });
export const updateReceivingRecord = (id, payload) => request(`/receiving/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const updateReceivingStatus = (id, payload) => request(`/receiving/${id}/status`, { method: 'POST', body: JSON.stringify(payload) });
export const deleteReceivingRecord = (id) => request(`/receiving/${id}`, { method: 'DELETE' });

// Payroll periods
export const fetchPayrollPeriods = (params = {}) => request(`/payroll-periods${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const fetchPayrollPeriod = (id) => request(`/payroll-periods/${id}`);
export const createPayrollPeriod = (payload) => request('/payroll-periods', { method: 'POST', body: JSON.stringify(payload) });
export const updatePayrollPeriod = (id, payload) => request(`/payroll-periods/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const importPayrollPeriodLines = (payload) => request('/payroll-periods/import', { method: 'POST', body: JSON.stringify(payload) });
export const postPayrollPeriod = (id, payload = {}) => request(`/payroll-periods/${id}/post`, { method: 'POST', body: JSON.stringify(payload) });
export const deletePayrollPeriod = (id) => request(`/payroll-periods/${id}`, { method: 'DELETE' });

// Roles, permissions, accounting setup admin
export const fetchPermissions = () => request('/roles-permissions/permissions');
export const fetchRoles = (activeOnly = false) => request(`/roles-permissions/roles?active_only=${String(!!activeOnly)}`);
export const createRole = (payload) => request('/roles-permissions/roles', { method: 'POST', body: JSON.stringify(payload) });
export const updateRole = (id, payload) => request(`/roles-permissions/roles/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteRole = (id) => request(`/roles-permissions/roles/${id}`, { method: 'DELETE' });
export const updateRolePermissions = (id, permissionKeys) => request(`/roles-permissions/roles/${id}/permissions`, { method: 'POST', body: JSON.stringify({ permission_keys: permissionKeys }) });
export const fetchUserRoles = (userId) => request(`/roles-permissions/users/${userId}/roles`);
export const assignUserRoles = (userId, roleIds) => request(`/roles-permissions/users/${userId}/roles`, { method: 'POST', body: JSON.stringify({ role_ids: roleIds }) });
export const fetchUserEffectivePermissions = (userId) => request(`/roles-permissions/users/${userId}/permissions`);
export const updateUserPermissionOverrides = (userId, overrides) => request(`/roles-permissions/users/${userId}/overrides`, { method: 'POST', body: JSON.stringify({ overrides }) });

export const fetchChartAccounts = (activeOnly = false) => request(`/chart-of-accounts?active_only=${String(!!activeOnly)}`);
export const createChartAccount = (payload) => request('/chart-of-accounts', { method: 'POST', body: JSON.stringify(payload) });
export const updateChartAccount = (id, payload) => request(`/chart-of-accounts/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteChartAccount = (id) => request(`/chart-of-accounts/${id}`, { method: 'DELETE' });

export const fetchAccountMappings = (params = {}) => request(`/account-mappings${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const createAccountMapping = (payload) => request('/account-mappings', { method: 'POST', body: JSON.stringify(payload) });
export const updateAccountMapping = (id, payload) => request(`/account-mappings/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
export const deleteAccountMapping = (id) => request(`/account-mappings/${id}`, { method: 'DELETE' });

export const fetchIntegrationReviewItems = (params = {}) => request(`/integration-review${Object.keys(params).length ? `?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== null && typeof v !== 'undefined')).toString()}` : ''}`);
export const fetchIntegrationReviewSummary = () => request('/integration-review/summary');
export const fetchIntegrationReviewItem = (id) => request(`/integration-review/${id}`);
export const acceptIntegrationReviewItem = (id, payload = {}) => request(`/integration-review/${id}/accept`, { method:'POST', body: JSON.stringify(payload) });
export const rejectIntegrationReviewItem = (id, payload = {}) => request(`/integration-review/${id}/reject`, { method:'POST', body: JSON.stringify(payload) });
export const retryIntegrationReviewItem = (id, payload = {}) => request(`/integration-review/${id}/retry`, { method:'POST', body: JSON.stringify(payload) });
