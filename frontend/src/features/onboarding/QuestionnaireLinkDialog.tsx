/** Creates a fresh single-use questionnaire link (30 days) and shows it once to copy. */
import { Copy } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Dialog } from '@/components/ui/Dialog';
import { useToast } from '@/components/ui/Toast';
import { onboardingKeys, sendQuestionnaire } from '@/features/onboarding/api';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '@/lib/api-client';
import { formatDate } from '@/lib/format';

export function QuestionnaireLinkDialog({
  clientId,
  open,
  onClose,
}: {
  clientId: string;
  open: boolean;
  onClose(): void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [link, setLink] = useState<{ url: string; expires: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sent = useRef(false);

  useEffect(() => {
    if (!open) {
      sent.current = false;
      return;
    }
    if (sent.current) return; // one link per opening (StrictMode runs effects twice)
    sent.current = true;
    setLink(null);
    setError(null);
    sendQuestionnaire(clientId)
      .then((result) => {
        setLink({ url: result.url, expires: result.expires_at });
        queryClient.setQueryData(onboardingKeys.detail(clientId), result.onboarding);
        void queryClient.invalidateQueries({ queryKey: ['clients', 'activity', clientId] });
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : 'Something went wrong. Try again.'),
      );
  }, [open, clientId, queryClient]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Onboarding questionnaire link"
      footer={<Button onClick={onClose}>Done</Button>}
    >
      {error ? <Alert tone="bad">{error}</Alert> : null}
      {!link && !error ? <p className="text-muted">Creating the link…</p> : null}
      {link ? (
        <div className="flex flex-col gap-3">
          <p className="text-muted">
            Send this link to the client. It works once, until {formatDate(link.expires)}; any
            earlier link no longer works. The client can save a draft and come back.
          </p>
          <div className="flex gap-2">
            <input
              readOnly
              aria-label="Questionnaire link"
              data-testid="questionnaire-link"
              className="input flex-1 font-mono text-xs"
              value={link.url}
              onFocus={(e) => e.currentTarget.select()}
            />
            <Button
              onClick={() => {
                void navigator.clipboard?.writeText(link.url);
                toast({ title: 'Link copied.' });
              }}
            >
              <Copy aria-hidden className="size-4" />
              Copy
            </Button>
          </div>
        </div>
      ) : null}
    </Dialog>
  );
}
