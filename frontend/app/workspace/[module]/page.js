import ModuleWorkspace from '../../../components/ModuleWorkspace';

export default function Page({ params }) {
  return <ModuleWorkspace moduleSlug={params.module} />;
}
