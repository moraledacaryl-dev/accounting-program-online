import { permanentRedirect } from 'next/navigation';

export default function TreasuryLegacyPage() {
  permanentRedirect('/cashflow');
}
