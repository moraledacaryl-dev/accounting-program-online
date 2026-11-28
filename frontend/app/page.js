import { redirect } from 'next/navigation';

export default function HomePage() {
  redirect(process.env.NEXT_PUBLIC_ACCOUNTING_TRAINING==='1'?'/training':'/dashboard');
}
