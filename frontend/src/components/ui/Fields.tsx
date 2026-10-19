/**
 * Labelled select and textarea fields matching TextField (mockup forms: "*" for
 * required, hint/error line, optional character counter on textareas).
 */
import {
  forwardRef,
  useId,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react';

import { cn } from '@/lib/utils';

interface Common {
  label: string;
  error?: string;
  hint?: ReactNode;
}

export interface SelectFieldProps extends Common, SelectHTMLAttributes<HTMLSelectElement> {
  options: readonly { value: string; label: string }[];
  /** First, empty option (e.g. "Choose…"). */
  placeholder?: string;
}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(function SelectField(
  { label, error, hint, options, placeholder, id, className, ...props },
  ref,
) {
  const generated = useId();
  const fieldId = id ?? generated;
  const message = error ?? hint;
  return (
    <div className="label">
      <label htmlFor={fieldId}>{label}</label>
      <select
        ref={ref}
        id={fieldId}
        className={cn('input', error && 'border-bad', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? `${fieldId}-message` : undefined}
        {...props}
      >
        {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {message ? (
        <span
          id={`${fieldId}-message`}
          className={cn('text-[12.5px] font-normal', error ? 'text-bad' : 'text-faint')}
        >
          {message}
        </span>
      ) : null}
    </div>
  );
});

export interface TextAreaFieldProps extends Common, TextareaHTMLAttributes<HTMLTextAreaElement> {
  /** Show "n/max" under the field (needs maxLength and a controlled or watched value). */
  count?: number;
}

export const TextAreaField = forwardRef<HTMLTextAreaElement, TextAreaFieldProps>(
  function TextAreaField({ label, error, hint, count, id, className, maxLength, ...props }, ref) {
    const generated = useId();
    const fieldId = id ?? generated;
    const message = error ?? hint;
    return (
      <div className="label">
        <label htmlFor={fieldId}>{label}</label>
        <div className="relative">
          <textarea
            ref={ref}
            id={fieldId}
            maxLength={maxLength}
            className={cn(
              'input min-h-24 w-full resize-y',
              count !== undefined && 'pb-6',
              error && 'border-bad',
              className,
            )}
            aria-invalid={error ? true : undefined}
            aria-describedby={message ? `${fieldId}-message` : undefined}
            {...props}
          />
          {count !== undefined && maxLength ? (
            <span
              aria-hidden
              className="pointer-events-none absolute right-3 bottom-2 text-[11.5px] font-normal text-faint"
            >
              {count}/{maxLength}
            </span>
          ) : null}
        </div>
        {message ? (
          <span
            id={`${fieldId}-message`}
            className={cn('text-[12.5px] font-normal', error ? 'text-bad' : 'text-faint')}
          >
            {message}
          </span>
        ) : null}
      </div>
    );
  },
);
