/**
 * Shared create/edit form for a client (fields from the clickable demo's
 * "New client" form). Duplicate rules are enforced by the API:
 * - duplicate domain → hard error;
 * - similar name → error until "This is a different business" is ticked.
 */
import { zodResolver } from '@hookform/resolvers/zod';
import { useId } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Alert } from '@/components/ui/Alert';
import { Button, LinkButton } from '@/components/ui/Button';
import { TextField } from '@/components/ui/Field';
import { useAccountManagers } from '@/features/clients/api';
import { ApiError } from '@/lib/api-client';

const optional = (max: number) => z.string().trim().max(max, `Use at most ${max} characters.`);

export const clientFormSchema = z.object({
  name: z.string().trim().min(1, "Enter the client's legal or business name.").max(200),
  website: optional(300),
  industry: optional(120),
  contactName: optional(200),
  contactEmail: z.union([z.literal(''), z.email('Enter a valid e-mail address.')]),
  accountManagerId: z.string().min(1, 'Choose an Account Manager.'),
  confirmDifferentBusiness: z.boolean(),
});
export type ClientFormValues = z.infer<typeof clientFormSchema>;

export const emptyClientForm: ClientFormValues = {
  name: '',
  website: '',
  industry: '',
  contactName: '',
  contactEmail: '',
  accountManagerId: '',
  confirmDifferentBusiness: false,
};

/** Form values → API body (blank strings become null). */
export function toClientBody(values: ClientFormValues) {
  const blank = (v: string) => (v.trim() === '' ? null : v.trim());
  return {
    name: values.name.trim(),
    website: blank(values.website),
    industry: blank(values.industry),
    contact_name: blank(values.contactName),
    contact_email: blank(values.contactEmail),
    account_manager_id: values.accountManagerId,
    confirm_different_business: values.confirmDifferentBusiness,
  };
}

export interface ClientFormProps {
  defaultValues: ClientFormValues;
  submitLabel: string;
  cancelTo: string;
  onSubmit(values: ClientFormValues): Promise<void>;
}

export function ClientForm({ defaultValues, submitLabel, cancelTo, onSubmit }: ClientFormProps) {
  const managerId = useId();
  const dupId = useId();
  const managers = useAccountManagers();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ClientFormValues>({ resolver: zodResolver(clientFormSchema), defaultValues });

  const submit = handleSubmit(async (values) => {
    try {
      await onSubmit(values);
    } catch (error) {
      setError('root', {
        type: error instanceof ApiError ? String(error.details.reason ?? error.code) : 'unknown',
        message: error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
      });
    }
  });

  const similarName = errors.root?.type === 'similar_name';

  return (
    <form className="flex flex-col gap-3" onSubmit={submit} noValidate>
      {errors.root?.message ? (
        <Alert tone={similarName ? 'warn' : 'bad'} title={similarName ? 'Possible duplicate' : undefined}>
          {errors.root.message}
        </Alert>
      ) : null}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
        <TextField label="Legal / business name *" error={errors.name?.message} {...register('name')} />
        <TextField
          label="Website"
          placeholder="example.com"
          error={errors.website?.message}
          {...register('website')}
        />
        <TextField label="Industry" error={errors.industry?.message} {...register('industry')} />
        <div className="label">
          <label htmlFor={managerId}>Account Manager *</label>
          <select
            id={managerId}
            className="input"
            aria-invalid={errors.accountManagerId ? true : undefined}
            {...register('accountManagerId')}
          >
            <option value="">{managers.isPending ? 'Loading…' : 'Choose…'}</option>
            {managers.data?.map((manager) => (
              <option key={manager.id} value={manager.id}>
                {manager.full_name}
              </option>
            ))}
          </select>
          {errors.accountManagerId?.message ? (
            <span className="text-[12.5px] font-normal text-bad">{errors.accountManagerId.message}</span>
          ) : null}
        </div>
        <TextField
          label="Primary contact"
          error={errors.contactName?.message}
          {...register('contactName')}
        />
        <TextField
          label="Contact e-mail"
          type="email"
          error={errors.contactEmail?.message}
          {...register('contactEmail')}
        />
      </div>
      <label
        htmlFor={dupId}
        className={`flex items-center gap-2 text-[13px] ${similarName ? 'font-medium text-warn' : ''}`}
      >
        <input id={dupId} type="checkbox" {...register('confirmDifferentBusiness')} />
        This is a different business (override a possible-duplicate warning)
      </label>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : submitLabel}
        </Button>
        <LinkButton to={cancelTo}>Cancel</LinkButton>
      </div>
    </form>
  );
}
