/**
 * Sign in (Firebase Auth → app session, ADR-0009). PROVISIONAL markup (the
 * clickable demo has no sign-in page). TODO(pilot-port): match 00-login.png.
 */
import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useLocation, useNavigate } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { Link } from '@/components/ui/Link';
import { errorMessage, loginSchema, type LoginForm } from '@/features/auth/schemas';
import { ApiError } from '@/lib/api-client';
import { EmailNotVerifiedError, useAuth } from '@/lib/auth-context';

type Resend = 'idle' | 'sending' | 'sent' | 'failed';

function VerifyEmailNotice({ onResend }: { onResend(): Promise<void> }) {
  const [state, setState] = useState<Resend>('idle');
  async function resend() {
    setState('sending');
    try {
      await onResend();
      setState('sent');
    } catch {
      setState('failed');
    }
  }
  return (
    <Alert tone="warn" title="Verify your e-mail address">
      <p>We sent a verification link when your account was set up. Open it, then sign in again.</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button size="sm" onClick={resend} disabled={state === 'sending' || state === 'sent'}>
          {state === 'sent' ? 'Sent' : 'Resend verification e-mail'}
        </Button>
        {state === 'sent' ? <span>Check your inbox.</span> : null}
        {state === 'failed' ? <span>Couldn't send it. Try signing in again.</span> : null}
      </div>
    </Alert>
  );
}

export function LoginPage() {
  const { status, signIn, resendVerification } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';
  const [unverified, setUnverified] = useState(false);
  const [pending, setPending] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  if (status === 'authenticated') return <Navigate to={from} replace />;

  const onSubmit = handleSubmit(async ({ email, password }) => {
    setUnverified(false);
    setPending(false);
    try {
      await signIn(email, password);
      navigate(from, { replace: true });
    } catch (error) {
      if (error instanceof EmailNotVerifiedError) setUnverified(true);
      else if (error instanceof ApiError && error.code === 'pending_approval') setPending(true);
      else setError('root', { message: errorMessage(error) });
    }
  });

  return (
    <>
      <h1 className="text-[21px] leading-tight font-bold">Sign in</h1>
      <form className="mt-5 flex flex-col gap-3" onSubmit={onSubmit} noValidate>
        {errors.root?.message ? <Alert tone="bad">{errors.root.message}</Alert> : null}
        {unverified ? <VerifyEmailNotice onResend={resendVerification} /> : null}
        {pending ? (
          <Alert tone="info" title="Waiting for approval">
            Your account is waiting for an administrator to approve it. You'll be able to sign in
            once it's approved.
          </Alert>
        ) : null}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register('email')}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register('password')}
        />
        <Button type="submit" variant="primary" className="justify-center" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </Button>
        <Link className="link self-start text-xs" to="/forgot-password">
          Forgot password?
        </Link>
      </form>
      <p className="mt-5 border-t border-line-soft pt-4 text-center text-[13px] text-muted">
        Don't have an account?{' '}
        <Link className="link" to="/signup">
          Sign up
        </Link>
      </p>
    </>
  );
}

export { LoginPage as Component };
