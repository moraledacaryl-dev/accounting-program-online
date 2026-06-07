export function stayIncludesDay(row, dayISO) {
  const checkIn = String(row?.check_in || '');
  const checkOut = String(row?.check_out || '');
  if (!checkIn || !dayISO) return false;
  if (!checkOut || checkOut <= checkIn) return checkIn === dayISO;
  return checkIn <= dayISO && dayISO < checkOut;
}
