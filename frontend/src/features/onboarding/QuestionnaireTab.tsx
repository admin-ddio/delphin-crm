/** Client › Questionnaire (Screen 4): link status, then the wizard (staff draft / record). */
import { Send } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import type { ClientDetail } from '@/features/clients/api';
import {
  onboardingApi,
  useOnboarding,
  useOnboardingAction,
  type OnboardingDetail,
} from '@/features/onboarding/api';
import { QuestionnaireLinkDialog } from '@/features/onboarding/QuestionnaireLinkDialog';
import { QuestionnaireWizard } from '@/features/onboarding/QuestionnaireWizard';
import { ApiError } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';

const STATUS = {
  none: { label: 'Not sent', tone: 'neutral' },
  sent: { label: 'Sent · awaiting client', tone: 'warn' },
  submitted: { label: 'Submitted', tone: 'ok' },
} as const;

export function QuestionnaireTab({ client }: { client: ClientDetail }) {
  const onboarding = useOnboarding(client.id);
  const action = useOnboardingAction(client.id);
  const { toast } = useToast();
  const [linkOpen, setLinkOpen] = useState(false);
  const data = onboarding.data;
  if (!data) return <EmptyState title="Loading questionnaire…" />;
  const q = data.questionnaire;
  const manage = data.permissions.manage;
  const status = STATUS[q.status];

  const run = async (call: () => Promise<OnboardingDetail>, done: string) => {
    try {
      await action.mutateAsync(call);
      toast({ title: done });
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
        tone: 'error',
      });
      throw error;
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Card className="flex flex-wrap items-center justify-between gap-4 px-6 py-5">
        <div className="flex min-w-[260px] flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-lg font-semibold">Client Questionnaire</h2>
            <Badge tone={status.tone}>{status.label}</Badge>
          </div>
          <p className="text-muted">
            Understand your client's business to build the right strategy.
          </p>
          <div className="flex max-w-md items-center gap-3 text-sm">
            <span className="whitespace-nowrap">Onboarding Progress</span>
            <div className="flex-1">
              <Progress value={data.progress} label="Onboarding progress" />
            </div>
          </div>
          <p className="text-xs text-muted">
            {q.submitted_at
              ? `Submitted ${formatDateTime(q.submitted_at)} by ${q.source === 'staff' ? 'the team' : 'the client'}`
              : q.sent_at
                ? `Link sent ${formatDateTime(q.sent_at)}`
                : 'Fill it in with the client here, or send them the link.'}
            {q.updated_at && !q.submitted_at
              ? ` · Draft saved ${formatDateTime(q.updated_at)}`
              : ''}
          </p>
        </div>
        {manage && q.status !== 'submitted' ? (
          <Button onClick={() => setLinkOpen(true)}>
            <Send aria-hidden className="size-4" />
            {q.status === 'sent' ? 'Send a new link' : 'Send questionnaire link'}
          </Button>
        ) : null}
      </Card>
      <QuestionnaireWizard
        key={`${q.status}-${q.updated_at ?? ''}`}
        clientName={client.name}
        form={q}
        allowDownload
        readOnly={!manage || q.status === 'submitted'}
        submitLabel="Record client's answers"
        onSaveDraft={(answers) =>
          run(() => onboardingApi.saveDraft(client.id, answers), 'Draft saved.')
        }
        onSubmit={(answers) =>
          run(() => onboardingApi.submitAnswers(client.id, answers), "Client's answers recorded.")
        }
      />
      <QuestionnaireLinkDialog
        clientId={client.id}
        open={linkOpen}
        onClose={() => setLinkOpen(false)}
      />
    </div>
  );
}
