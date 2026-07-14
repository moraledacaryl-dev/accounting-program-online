import { redirect } from 'next/navigation';
export default function LegacyCashflowRedirect() { redirect('/cashflow?tab=ledger'); }
