import { redirect } from 'next/navigation';

export default function LegacyRoomSetupPage() {
  redirect('/room-types');
}
