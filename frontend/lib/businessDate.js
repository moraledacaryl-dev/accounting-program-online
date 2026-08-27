export const BUSINESS_TIME_ZONE = 'Asia/Manila';

function partsFor(date = new Date()) {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone: BUSINESS_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  const parts = Object.fromEntries(
    formatter.formatToParts(date)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value]),
  );
  return parts;
}

export function businessDateISO(date = new Date()) {
  const parts = partsFor(date);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function businessMonthISO(date = new Date()) {
  return businessDateISO(date).slice(0, 7);
}

export function shiftBusinessDate(days, date = new Date()) {
  const current = businessDateISO(date);
  const [year, month, day] = current.split('-').map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day + Number(days || 0), 12, 0, 0));
  return shifted.toISOString().slice(0, 10);
}
