/** /account: your profile and password. PROVISIONAL layout (demo panels). */
import { zodResolver } from '@hookform/resolvers/zod';
import {
  signInWithEmailAndPassword,
  signOut as firebaseSignOut,
  updatePassword,
} from 'firebase/auth';
import { useForm } from 'react-hook-form';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { KeyValue } from '@/components/ui/Data';
import { TextField } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  changePasswordSchema,
  errorMessage,
  PASSWORD_MIN_LENGTH,
  type ChangePasswordForm,
} from '@/features/auth/schemas';
import { api, unwrap } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { firebaseAuth } from '@/lib/firebase';
import { ROLE_LABELS, type RoleKey } from '@/lib/permissions';

const roleLabel = (role: string) => ROLE_LABELS[role as RoleKey] ?? role;

export function Component() {
  const { actor } = useAuth();
  const { toast } = useToast();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordForm>({ resolver: zodResolver(changePasswordSchema) });

  const onSubmit = handleSubmit(async ({ currentPassword, newPassword }) => {
    if (!actor) return;
    const auth = firebaseAuth();
    try {
      // Firebase needs a fresh sign-in to change a password: re-check the current one.
      const credential = await signInWithEmailAndPassword(auth, actor.email, currentPassword);
      await updatePassword(credential.user, newPassword);
      unwrap(await api.POST('/api/v1/auth/sessions/revoke-others'));
      reset();
      toast({ title: 'Password changed. Other sessions have been signed out.' });
    } catch (error) {
      const code = (error as { code?: string }).code;
      const wrongCurrent = code === 'auth/invalid-credential' || code === 'auth/wrong-password';
      setError('root', {
        message: wrongCurrent ? 'The current password is incorrect.' : errorMessage(error),
      });
    } finally {
      await firebaseSignOut(auth);
    }
  });

  if (!actor) return null;

  return (
    <>
      <PageHeader title="My account" />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] items-start gap-4">
        <Panel title="Profile">
          <KeyValue
            items={[
              ['Name', actor.fullName],
              ['Email', <span className="code">{actor.email}</span>],
              [
                'Role',
                <span className="flex flex-wrap gap-1">
                  {actor.roles.map((role) => (
                    <Badge key={role} tone={role === 'super_admin' ? 'info' : 'accent'}>
                      {roleLabel(role)}
                    </Badge>
                  ))}
                </span>,
              ],
            ]}
          />
        </Panel>
        <Panel
          title="Change password"
          description="Other sessions are signed out when you change it."
        >
          <form className="flex flex-col gap-3" onSubmit={onSubmit} noValidate>
            {errors.root?.message ? <Alert tone="bad">{errors.root.message}</Alert> : null}
            <TextField
              label="Current password"
              type="password"
              autoComplete="current-password"
              error={errors.currentPassword?.message}
              {...register('currentPassword')}
            />
            <TextField
              label="New password"
              type="password"
              autoComplete="new-password"
              hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
              error={errors.newPassword?.message}
              {...register('newPassword')}
            />
            <TextField
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              error={errors.confirm?.message}
              {...register('confirm')}
            />
            <div>
              <Button type="submit" variant="primary" disabled={isSubmitting}>
                Change password
              </Button>
            </div>
          </form>
        </Panel>
      </div>
    </>
  );
}
