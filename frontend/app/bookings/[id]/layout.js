import BookingDetailPage from './page';
import { positiveIntegerRouteParam } from '../../../lib/routeParams';

export default async function BookingDetailLayout({ params }) {
  const { id } = await params;
  const bookingId = positiveIntegerRouteParam(String(id || ''));
  if (!bookingId) {
    return (
      <section className="section">
        <h1>Booking</h1>
        <p className="error-text">Invalid booking ID.</p>
      </section>
    );
  }
  return <BookingDetailPage params={{ id: String(bookingId) }} />;
}
