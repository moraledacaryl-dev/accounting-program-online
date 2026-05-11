export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function money(value) {
  return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function ensureString(value, fallback = '') {
  return String(value ?? fallback);
}
