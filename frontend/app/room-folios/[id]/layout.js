import DetailPage from './page';
import { positiveIntegerRouteParam } from '../../../lib/routeParams';

export default async function DetailLayout({ params }) {
  const values = await params;
  const routeId = positiveIntegerRouteParam(String(values?.id || ''));
  if (!routeId) return <p className="error-text">Invalid route identifier.</p>;
  return <DetailPage params={{ id: String(routeId) }} />;
}
