export function positiveIntegerRouteParam(value) {
  const scalar = Array.isArray(value) ? value[0] : value;
  if (typeof scalar !== 'string' || scalar.trim() === '') return null;
  const parsed = Number(scalar);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
}
