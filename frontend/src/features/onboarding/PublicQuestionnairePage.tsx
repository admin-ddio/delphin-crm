/**
 * /q/:token: the questionnaire a client fills in from the link their Account
 * Manager sent. No sign-in (the single-use token is the credential), no app chrome.
 */
import { useId, useState, type FormEvent } from 'react';
import { useParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { submitPublicQuestionnaire, usePublicQuestionnaire } from '@/features/onboarding/api';
import { ApiError } from '@/lib/api-client';

function Header({ subtitle }: { subtitle?: string }) {
  return (
    <div className="mb-6 flex items-center gap-2.5">
      <span aria-hidden className="grid size-[30px] place-items-center rounded-[7px] bg-accent font-bold text-on-accent">
        D
      </span>
      <div>
        <b className="block text-sm leading-[1.1]">Delphin Digital</b>
        <small className="block text-[11px] text-muted">{subtitle ?? 'Client onboarding'}</small>
      </div>
    </div>
  );
}

export function Component() {
  const { token = '' } = useParams();
  const questionnaire = usePublicQuestionnaire(token);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const formId = useId();

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await submitPublicQuestionnaire(token, answers);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't send your answers. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (questionnaire.isPending) {
    return (
      <>
        <Header />
        <h1 className="text-[21px] font-bold">Client questionnaire</h1>
        <p className="mt-2 text-muted">Loading…</p>
      </>
    );
  }
  if (questionnaire.isError || !questionnaire.data) {
    return (
      <>
        <Header />
        <h1 className="text-[21px] font-bold">Client questionnaire</h1>
        <Alert tone="bad" className="mt-4">
          This questionnaire link is invalid, already used or has expired. Ask your account manager
          for a new one.
        </Alert>
      </>
    );
  }
  if (done) {
    return (
      <>
        <Header />
        <h1 className="text-[21px] font-bold">Thank you</h1>
        <Alert tone="ok" className="mt-4" title="Your answers have been sent">
          Your account manager at Delphin Digital will be in touch about the next steps.
        </Alert>
      </>
    );
  }

  return (
    <>
      <Header subtitle={`Onboarding questionnaire for ${questionnaire.data.client_name}`} />
      <h1 className="text-[21px] font-bold">Client questionnaire</h1>
      <p className="mt-1 mb-5 text-muted">
        A few questions so we can plan your work. Every question needs an answer; this link works once.
      </p>
      <Panel>
        <form className="flex flex-col gap-4" onSubmit={submit}>
          {error ? <Alert tone="bad">{error}</Alert> : null}
          {questionnaire.data.questions.map((q) => (
            <div key={q.key} className="label">
              <label htmlFor={`${formId}-${q.key}`}>{q.label}</label>
              <textarea
                id={`${formId}-${q.key}`}
                className="input min-h-[70px] resize-y"
                required
                maxLength={4000}
                value={answers[q.key] ?? ''}
                onChange={(e) => setAnswers((a) => ({ ...a, [q.key]: e.target.value }))}
              />
            </div>
          ))}
          <div>
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? 'Sending…' : 'Send answers'}
            </Button>
          </div>
        </form>
      </Panel>
    </>
  );
}
