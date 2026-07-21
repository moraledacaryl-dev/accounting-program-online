import { notFound, permanentRedirect } from 'next/navigation';
import { workspaceRedirects } from '../../../lib/information-architecture';

export default async function WorkspaceRedirectPage({ params }) {
  const resolvedParams = await params;
  const target = workspaceRedirects[resolvedParams?.module];

  if (!target) notFound();
  permanentRedirect(target);
}
