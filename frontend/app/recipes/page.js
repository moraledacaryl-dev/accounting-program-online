import LegacyExternalModuleNotice from '../../components/LegacyExternalModuleNotice';
import { redirect } from 'next/navigation';

export default function RecipesPage() {
  redirect('/menu-items');
}