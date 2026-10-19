/**
 * /q/:token: the questionnaire a client fills in from the link their Account
 * Manager sent (same 7-step wizard as staff). No sign-in: the single-use token is
 * the credential. Drafts can be saved and resumed with the same link.
 */
import { Building2 } from 'lucide-react';
import { useState } from 'react';
import { useParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { useToast } from '@/components/ui/Toast';
import {
  savePublicDraft,
  submitPublicQuestionnaire,
  usePublicQuestionnaire,
} from '@/features/onboarding/api';
import { QuestionnaireWizard } from '@/features/onboarding/QuestionnaireWizard';
import { ApiError } from '@/lib/api-client';

function Header() {
  return (
    <div className="mb-6 flex items-center gap-2.5">
      <span
        aria-hidden
        className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-[#7c5cff] to-[#4424cf] text-white"
      >
        <Building2 className="size-5" />
      </span>
      <div>
        <b className="block text-[15px] leading-[1.1]">Delphin Digital</b>
        <small className="block text-[11px] text-muted">Client onboarding</small>
      </div>
    </div>
  );
}

export function Component() {
  const { token = '' } = useParams();
  const questionnaire = usePublicQuestionnaire(token);
  const { toast } = useToast();
  const [done, setDone] = useState(false);
  const message = (err: unknown) =>
    err instanceof ApiError ? err.message : "Couldn't save your answers. Try again.";

  return (
    <div>
      <Header />
      {questionnaire.isPending ? <p className="text-muted">Loading…</p> : null}
      {questionnaire.isError ? (
        <>
          <h1 className="text-[26px] font-bold">Client questionnaire</h1>
          <Alert tone="bad">
            {questionnaire.error instanceof ApiError
              ? questionnaire.error.message
              : "Couldn't load the questionnaire. Reload the page to try again."}{' '}
            Ask your Account Manager for a new link.
          </Alert>
        </>
      ) : null}
      {done ? (
        <Alert tone="ok" title="Your answers have been sent">
          Thank you! Your Account Manager will be in touch about the next steps. You can close this
          page.
        </Alert>
      ) : null}
      {questionnaire.data && !done ? (
        <>
          <h1 className="text-[26px] font-bold">
            Onboarding questionnaire for {questionnaire.data.client_name}
          </h1>
          <p className="mt-1 mb-6 text-muted">
            Help us understand your business so we can build the right strategy. Save a draft any
            time and come back with the same link.
          </p>
          <QuestionnaireWizard
            clientName={questionnaire.data.client_name}
            form={questionnaire.data}
            submitLabel="Send answers"
            onSaveDraft={async (answers) => {
              try {
                await savePublicDraft(token, answers);
                toast({ title: 'Draft saved. Use the same link to continue later.' });
              } catch (err) {
                toast({ title: message(err), tone: 'error' });
              }
            }}
            onSubmit={async (answers) => {
              try {
                await submitPublicQuestionnaire(token, answers);
                setDone(true);
              } catch (err) {
                toast({ title: message(err), tone: 'error' });
              }
            }}
          />
        </>
      ) : null}
    </div>
  );
}
