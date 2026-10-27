/** /clients/new – Screen 2 (product mockup): "Create New Client", Cancel / Save & Continue. */
import { ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Button, LinkButton } from '@/components/ui/Button';
import { Link } from '@/components/ui/Link';
import { useToast } from '@/components/ui/Toast';
import { useCreateClient } from '@/features/clients/api';
import { ClientForm, emptyClientForm, toClientBody } from '@/features/clients/ClientForm';
import { uploadDocument } from '@/features/documents/api';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { can, P, ROLE_LABELS, type RoleKey } from '@/lib/permissions';

export function Component() {
  const { actor } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const create = useCreateClient();
  const [busy, setBusy] = useState(false);

  const header = (actions?: React.ReactNode) => (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-[26px] leading-tight font-bold tracking-[-0.02em]">
          Create New Client
        </h1>
        <nav
          aria-label="Breadcrumb"
          className="mt-2 flex items-center gap-2 text-[15px] text-muted"
        >
          <Link to="/clients" className="text-accent hover:underline">
            Clients
          </Link>
          <ChevronRight aria-hidden className="size-4" />
          <span>Create New Client</span>
        </nav>
      </div>
      {actions}
    </div>
  );

  if (!actor || !can(actor.permissions, P.clientsCreate)) {
    const role = ROLE_LABELS[actor?.roles[0] as RoleKey] ?? 'Your role';
    return (
      <>
        {header()}
        <Alert tone="bad" title="Access denied">
          {role} can't create clients.
        </Alert>
      </>
    );
  }

  return (
    <>
      {header(
        <div className="flex gap-3">
          <LinkButton to="/clients" className="px-5 py-2.5">
            Cancel
          </LinkButton>
          <Button
            type="submit"
            form="client-form"
            variant="primary"
            className="px-5 py-2.5"
            disabled={busy}
          >
            {busy ? 'Saving…' : 'Save & Continue'}
            <ChevronRight aria-hidden className="size-4" />
          </Button>
        </div>,
      )}
      <ClientForm
        formId="client-form"
        withUpload
        withServices
        defaultValues={{ ...emptyClientForm, accountManagerId: actor.id }}
        onBusyChange={setBusy}
        onSubmit={async (values, contract, services) => {
          const client = await create.mutateAsync({ ...toClientBody(values), services });
          if (contract) {
            try {
              await uploadDocument(client.id, contract, { name: 'Contracts' });
            } catch (error) {
              toast({
                title: `Client created, but the contract didn't upload: ${
                  error instanceof ApiError ? error.message : 'try again from Documents'
                }`,
                tone: 'error',
              });
            }
          }
          toast({
            title: `Client ${client.name} created (${client.code}). Onboarding has started.`,
          });
          navigate(`/clients/${client.id}`);
        }}
      />
    </>
  );
}
