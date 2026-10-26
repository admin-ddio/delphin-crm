/** Form validation mirroring backend/app/modules/auth/schemas.py. */
import { z } from 'zod';

import { ApiError } from '@/lib/api-client';
import { firebaseErrorMessage } from '@/lib/firebase';

export const PASSWORD_MIN_LENGTH = 12;

const email = z.email('Enter a valid e-mail address.');

const newPassword = z
  .string()
  .min(PASSWORD_MIN_LENGTH, `Use at least ${PASSWORD_MIN_LENGTH} characters.`)
  .max(200, 'Use at most 200 characters.');

export const loginSchema = z.object({
  email,
  password: z.string().min(1, 'Enter your password.'),
});
export type LoginForm = z.infer<typeof loginSchema>;

export const signupSchema = z
  .object({
    fullName: z
      .string()
      .trim()
      .min(1, 'Enter your full name.')
      .max(200, 'Use at most 200 characters.'),
    email,
    password: newPassword,
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, {
    path: ['confirm'],
    message: "The passwords don't match.",
  });
export type SignupForm = z.infer<typeof signupSchema>;

export const forgotSchema = z.object({ email });
export type ForgotForm = z.infer<typeof forgotSchema>;

export const setPasswordSchema = z
  .object({ password: newPassword, confirm: z.string() })
  .refine((v) => v.password === v.confirm, {
    path: ['confirm'],
    message: "The passwords don't match.",
  });
export type SetPasswordForm = z.infer<typeof setPasswordSchema>;

export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Enter your current password.'),
    newPassword,
    confirm: z.string(),
  })
  .refine((v) => v.newPassword === v.confirm, {
    path: ['confirm'],
    message: "The passwords don't match.",
  });
export type ChangePasswordForm = z.infer<typeof changePasswordSchema>;

/** Human message for a failed API or Firebase call (neither leaks internals). */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (typeof (error as { code?: unknown } | null)?.code === 'string') {
    return firebaseErrorMessage(error);
  }
  return "Couldn't reach the server. Check your connection and try again.";
}
