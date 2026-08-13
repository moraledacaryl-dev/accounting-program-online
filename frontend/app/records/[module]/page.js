import { permanentRedirect } from 'next/navigation';

export default async function LegacyRecordsPage({ params }) {
  const { module } = await params;
  const safeModule = encodeURIComponent(String(module || ''));
  permanentRedirect(`/workspace/${safeModule}?tab=records`);
}
