/**
 * Labelled form field with a hint/error line. PROVISIONAL visuals (the demo's
 * `label.fld`); replace with the pilot's form field primitives when ported.
 * The <label> holds only the label text so the input's accessible name is exact;
 * the hint/error is linked with aria-describedby. Forwards the ref for react-hook-form.
 */
import { forwardRef, useId, type InputHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, error, hint, id, className, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const messageId = `${inputId}-message`;
  const message = error ?? hint;
  return (
    <div className="label">
      <label htmlFor={inputId}>{label}</label>
      <input
        ref={ref}
        id={inputId}
        className={cn('input', error && 'border-bad', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? messageId : undefined}
        {...props}
      />
      {message ? (
        <span
          id={messageId}
          className={cn('text-[12.5px] font-normal', error ? 'text-bad' : 'text-faint')}
        >
          {message}
        </span>
      ) : null}
    </div>
  );
});
