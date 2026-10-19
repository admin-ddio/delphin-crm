/** /clients/new (wording from the clickable demo's "New client" form). */
import { useNavigate } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Panel } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import { useCreateClient } from '@/features/clients/api';
import { ClientForm, emptyClientForm, toClientBody } from '@/features/clients/ClientForm';
import { useAuth } from '@/lib/auth-context';
import { can, P, ROLE_LABELS, type RoleKey } from '@/lib/permissions';

const crumb = { label: 'Clients', to: '/clients' };

export function Component() {
  const { actor } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const create = useCreateClient();

  if (!actor || !can(actor.permissions, P.clientsCreate)) {
    const role = ROLE_LABELS[actor?.roles[0] as RoleKey] ?? 'Your role';
    return (
      <>
        <PageHeader title="New client" crumb={crumb} />
        <Alert tone="bad" title="Access denied">
          {role} can't create clients.
        </Alert>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="New client"
        crumb={crumb}
        description="Step 2 of onboarding. The onboarding checklist and the access checklist (GSC, GA4, CMS, Ahrefs, Google Drive) will be created automatically once onboarding is ported."
      />
      <Panel>
        <ClientForm
          defaultValues={{ ...emptyClientForm, accountManagerId: actor.id }}
          submitLabel="Create client"
          cancelTo="/clients"
          onSubmit={async (values) => {
            const client = await create.mutateAsync(toClientBody(values));
            toast({ title: `Client ${client.name} created (${client.code}).` });
            navigate(`/clients/${client.id}`);
          }}
        />
      </Panel>
    </>
  );
}
