import { permanentRedirect } from 'next/navigation';

export default function LegacyRecordsPage({ params }) {
  permanentRedirect(`/workspace/${params.module}?tab=records`);
}
