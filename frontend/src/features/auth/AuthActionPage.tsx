/**
 * /auth/action: our handler for Firebase e-mail links
 * (?mode=verifyEmail|resetPassword&oobCode=…).
 *
 * In a real project, point Firebase console → Authentication → Templates →
 * "Customize action URL" at https://<app>/auth/action. Without that, Firebase's
 * hosted pages handle the links and send people back to /login.
 */
import { useQuery } from '@tanstack/react-query';
import { applyActionCode, confirmPasswordReset, verifyPasswordResetCode } from 'firebase/auth';
import { useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Link } from '@/components/ui/Link';
import { SetPasswordForm } from '@/features/auth/SetPasswordForm';
import { firebaseAuth, firebaseErrorMessage } from '@/lib/firebase';

function Page({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <h1 className="text-[21px] leading-tight font-bold">{title}</h1>
      <div className="mt-5 flex flex-col gap-3">{children}</div>
    </>
  );
}

const signInLink = (
  <Link className="link self-start" to="/login">
    Sign in
  </Link>
);

function VerifyEmail({ code }: { code: string }) {
  // A query (not an effect) so StrictMode/re-renders never apply the code twice.
  const result = useQuery({
    queryKey: ['auth-action', 'verifyEmail', code],
    queryFn: async () => {
      await applyActionCode(firebaseAuth(), code);
      return true;
    },
    retry: false,
    staleTime: Infinity,
  });
  return (
    <Page title="Verify e-mail">
      {result.isPending ? <p className="text-muted">Verifying…</p> : null}
      {result.isSuccess ? (
        <>
          <Alert tone="ok">Your e-mail address is verified. You can sign in now.</Alert>
          {signInLink}
        </>
      ) : null}
      {result.isError ? (
        <>
          <Alert tone="bad">{firebaseErrorMessage(result.error)}</Alert>
          {signInLink}
        </>
      ) : null}
    </Page>
  );
}

function ResetPassword({ code }: { code: string }) {
  const [done, setDone] = useState(false);
  const check = useQuery({
    queryKey: ['auth-action', 'resetPassword', code],
    queryFn: () => verifyPasswordResetCode(firebaseAuth(), code),
    retry: false,
    staleTime: Infinity,
  });
  return (
    <Page title="Reset password">
      {check.isPending ? <p className="text-muted">Checking the link…</p> : null}
      {check.isError ? (
        <>
          <Alert tone="bad">{firebaseErrorMessage(check.error)}</Alert>
          <Link className="link self-start" to="/forgot-password">
            Ask for a new link
          </Link>
        </>
      ) : null}
      {check.isSuccess && done ? (
        <>
          <Alert tone="ok">Your password has been changed. Sign in with the new password.</Alert>
          {signInLink}
        </>
      ) : null}
      {check.isSuccess && !done ? (
        <>
          <p className="text-muted">
            Choose a new password for <b className="text-fg">{check.data}</b>.
          </p>
          <SetPasswordForm
            submitLabel="Change password"
            onSubmit={async (password) => {
              await confirmPasswordReset(firebaseAuth(), code, password);
              setDone(true);
            }}
          />
        </>
      ) : null}
    </Page>
  );
}

export function Component() {
  const [params] = useSearchParams();
  const mode = params.get('mode');
  const code = params.get('oobCode');
  if (code && mode === 'verifyEmail') return <VerifyEmail code={code} />;
  if (code && mode === 'resetPassword') return <ResetPassword code={code} />;
  return (
    <Page title="Account link">
      <Alert tone="bad">This link is invalid or incomplete. Ask for a new one.</Alert>
      {signInLink}
    </Page>
  );
}
