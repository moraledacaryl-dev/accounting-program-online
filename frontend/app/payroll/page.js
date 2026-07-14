import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';
import { permanentRedirect } from 'next/navigation';

export default function PayrollLegacyPage() {
  permanentRedirect('/payroll-periods');
}