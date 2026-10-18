import type { ModuleKey } from '@/app/route-spec';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';

export function PlaceholderPage({ title, module }: { title: string; module: ModuleKey }) {
  return (
    <>
      <PageHeader title={title} />
      <Panel flush>
        <EmptyState
          title="Not yet ported. See PARITY.md"
          description={<span className="code">frontend/src/features/{module}/PARITY.md</span>}
        />
      </Panel>
    </>
  );
}
