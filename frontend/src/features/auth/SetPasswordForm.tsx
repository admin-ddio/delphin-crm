/** New password + confirmation, shared by password reset and account activation. */
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import {
  errorMessage,
  PASSWORD_MIN_LENGTH,
  setPasswordSchema,
  type SetPasswordForm as Values,
} from '@/features/auth/schemas';

export interface SetPasswordFormProps {
  submitLabel: string;
  onSubmit(password: string): Promise<void>;
}

export function SetPasswordForm({ submitLabel, onSubmit }: SetPasswordFormProps) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(setPasswordSchema) });

  const submit = handleSubmit(async ({ password }) => {
    try {
      await onSubmit(password);
    } catch (error) {
      setError('root', { message: errorMessage(error) });
    }
  });

  return (
    <form className="mt-5 flex flex-col gap-3" onSubmit={submit} noValidate>
      {errors.root?.message ? <Alert tone="bad">{errors.root.message}</Alert> : null}
      <TextField
        label="New password"
        type="password"
        autoComplete="new-password"
        hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
        error={errors.password?.message}
        {...register('password')}
      />
      <TextField
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        error={errors.confirm?.message}
        {...register('confirm')}
      />
      <Button type="submit" variant="primary" className="justify-center" disabled={isSubmitting}>
        {submitLabel}
      </Button>
    </form>
  );
}
