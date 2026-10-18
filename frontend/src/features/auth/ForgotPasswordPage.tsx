/**
 * Request a password-reset e-mail from Firebase. The answer is the same whether
 * or not the account exists (no account probing).
 */
import { zodResolver } from '@hookform/resolvers/zod';
import { sendPasswordResetEmail } from 'firebase/auth';
import { useState } from 'react';
import { useForm } from 'react-hook-form';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { Link } from '@/components/ui/Link';
import { errorMessage, forgotSchema, type ForgotForm } from '@/features/auth/schemas';
import { firebaseAuth, signInUrl } from '@/lib/firebase';

const SENT = "If an account exists for that e-mail, we've sent a link to reset the password.";
const SILENT_CODES = new Set(['auth/user-not-found', 'auth/invalid-email']);

export function Component() {
  const [sent, setSent] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ForgotForm>({ resolver: zodResolver(forgotSchema) });

  const onSubmit = handleSubmit(async ({ email }) => {
    try {
      await sendPasswordResetEmail(firebaseAuth(), email, { url: signInUrl() });
      setSent(true);
    } catch (error) {
      const code = (error as { code?: string }).code ?? '';
      if (SILENT_CODES.has(code)) setSent(true);
      else setError('root', { message: errorMessage(error) });
    }
  });

  return (
    <>
      <h1 className="text-[21px] leading-tight font-bold">Forgot password</h1>
      {sent ? (
        <div className="mt-5 flex flex-col gap-3">
          <Alert tone="ok">{SENT}</Alert>
          <Link className="link self-start text-xs" to="/login">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form className="mt-5 flex flex-col gap-3" onSubmit={onSubmit} noValidate>
          <p className="text-muted">
            Enter your e-mail and we'll send you a link to choose a new password.
          </p>
          {errors.root?.message ? <Alert tone="bad">{errors.root.message}</Alert> : null}
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            error={errors.email?.message}
            {...register('email')}
          />
          <Button type="submit" variant="primary" className="justify-center" disabled={isSubmitting}>
            Send reset link
          </Button>
          <Link className="link self-start text-xs" to="/login">
            Back to sign in
          </Link>
        </form>
      )}
    </>
  );
}
