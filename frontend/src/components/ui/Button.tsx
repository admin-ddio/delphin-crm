/**
 * PROVISIONAL (look from the clickable demo's `.btn`). Replace with a verbatim
 * port of the pilot's Button/LinkButton when reference/pilot/nextjs-app exists.
 */
import { forwardRef, type ButtonHTMLAttributes } from 'react';

import { Link, type LinkProps } from '@/components/ui/Link';
import { cn } from '@/lib/utils';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md';

const base =
  'inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-lg border font-medium whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-45';

const variants: Record<ButtonVariant, string> = {
  primary:
    'border-accent bg-accent text-on-accent shadow-sm hover:border-accent-strong hover:bg-accent-strong',
  secondary: 'border-line bg-surface text-fg hover:bg-sunk',
  ghost: 'border-transparent bg-transparent text-accent hover:bg-accent-soft',
  danger: 'border-bad/40 bg-surface text-bad hover:bg-bad-soft',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'px-2.5 py-1 text-[12.5px]',
  md: 'px-4 py-2 text-sm',
};

export function buttonClasses(variant: ButtonVariant = 'secondary', size: ButtonSize = 'md') {
  return cn(base, variants[variant], sizes[size]);
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, className, type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(buttonClasses(variant, size), className)}
      {...props}
    />
  );
});

export interface LinkButtonProps extends LinkProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function LinkButton({ variant, size, className, ...props }: LinkButtonProps) {
  return <Link className={cn(buttonClasses(variant, size), className)} {...props} />;
}
