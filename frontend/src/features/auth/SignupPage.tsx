/**
 * Self sign-up (/signup). Not a pilot route: added on request, see
 * docs/adr/0009 and modules/auth/PARITY.md.
 *
 * Firebase creates the login and sends the verification e-mail; the app records
 * the person as PENDING. They can sign in only after verifying the e-mail AND an
 * approver (users.approve) has assigned a role on Team & roles.
 */
import { zodResolver } from '@hookform/resolvers/zod';
import {
  createUserWithEmailAndPassword,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  updateProfile,
  type User,
} from 'firebase/auth';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { Link } from '@/components/ui/Link';
import {
  errorMessage,
  PASSWORD_MIN_LENGTH,
  signupSchema,
  type SignupForm,
} from '@/features/auth/schemas';
import { api, unwrap } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { firebaseAuth, signInUrl } from '@/lib/firebase';

/**
 * Create the Firebase login, or reuse it when a previous attempt got that far but
 * failed before the app recorded the sign-up (same password proves it's theirs).
 */
async function firebaseAccount(email: string, password: string, fullName: string): Promise<User> {
  const auth = firebaseAuth();
  try {
    const { user } = await createUserWithEmailAndPassword(auth, email, password);
    await updateProfile(user, { displayName: fullName });
    return user;
  } catch (error) {
    if ((error as { code?: string }).code !== 'auth/email-already-in-use') throw error;
    try {
      return (await signInWithEmailAndPassword(auth, email, password)).user;
    } catch {
      throw error;
    }
  }
}

export function Component() {
  const { status } = useAuth();
  const [done, setDone] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SignupForm>({ resolver: zodResolver(signupSchema) });

  if (status === 'authenticated') return <Navigate to="/dashboard" replace />;

  const onSubmit = handleSubmit(async ({ fullName, email, password }) => {
    const auth = firebaseAuth();
    try {
      const user = await firebaseAccount(email, password, fullName);
      if (!user.emailVerified) await sendEmailVerification(user, { url: signInUrl() });
      const idToken = await user.getIdToken();
      const result = unwrap(
        await api.POST('/api/v1/auth/register', {
          body: { id_token: idToken, full_name: fullName },
        }),
      );
      setDone(result.message);
    } catch (error) {
      setError('root', { message: errorMessage(error) });
    } finally {
      await firebaseSignOut(auth);
    }
  });

  return (
    <>
      <h1 className="text-[21px] leading-tight font-bold">Create account</h1>
      {done ? (
        <div className="mt-5 flex flex-col gap-3">
          <Alert tone="ok" title="Check your inbox">
            {done}
          </Alert>
          <Link className="link self-start" to="/login">
            Back to sign in
          </Link>
        </div>
      ) : (
        <form className="mt-5 flex flex-col gap-3" onSubmit={onSubmit} noValidate>
          <p className="text-muted">
            An administrator approves new accounts before they can sign in.
          </p>
          {errors.root?.message ? <Alert tone="bad">{errors.root.message}</Alert> : null}
          <TextField
            label="Full name"
            autoComplete="name"
            error={errors.fullName?.message}
            {...register('fullName')}
          />
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
            autoComplete="new-password"
            hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
            error={errors.password?.message}
            {...register('password')}
          />
          <TextField
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            error={errors.confirm?.message}
            {...register('confirm')}
          />
          <Button type="submit" variant="primary" className="justify-center" disabled={isSubmitting}>
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </Button>
          <p className="text-xs text-muted">
            Already have an account?{' '}
            <Link className="link" to="/login">
              Sign in
            </Link>
          </p>
        </form>
      )}
    </>
  );
}
