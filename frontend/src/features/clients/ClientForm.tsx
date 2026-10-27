/**
 * Screen 2 – Create / edit client (product mockup): Company Information, Primary
 * Contact, Account Manager, Contract Details and an optional contract upload; on create
 * also the Services bought (retainers and projects, at least one).
 * Duplicate rules are enforced by the API (duplicate domain → hard error; similar
 * name → error until "This is a different business" is ticked).
 */
import { zodResolver } from '@hookform/resolvers/zod';
import { Briefcase, Building2, FileText, Upload, UserRound, UserRoundCog } from 'lucide-react';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Alert } from '@/components/ui/Alert';
import { Avatar } from '@/components/ui/Avatar';
import { Card } from '@/components/ui/Card';
import { TextField } from '@/components/ui/Field';
import { SelectField, TextAreaField } from '@/components/ui/Fields';
import {
  BUSINESS_TYPES,
  COMPANY_SIZES,
  INDUSTRIES,
  PAYMENT_TERMS,
  useAccountManagers,
  type ClientCreate,
  type ClientDetail,
} from '@/features/clients/api';
import type { ServiceSelection } from '@/features/services/api';
import { ServicePicker, toSelections, type ServiceChoice } from '@/features/services/ServicePicker';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { COUNTRY_OPTIONS, DIAL_CODES } from '@/lib/countries';
import { formatBytes } from '@/lib/format';
import { can, P } from '@/lib/permissions';
import { cn } from '@/lib/utils';

const text = (max: number) => z.string().trim().max(max, `Use at most ${max} characters.`);
const required = (message: string, max: number) => text(max).min(1, message);
const email = z.union([z.literal(''), z.email('Enter a valid e-mail address.')]);

export const clientFormSchema = z
  .object({
    name: required('Enter the company name.', 200),
    website: text(300),
    industry: required('Choose an industry.', 120),
    businessType: z.string(),
    companySize: z.string(),
    country: required('Choose a country.', 2),
    description: text(500),
    contactName: required("Enter the contact's name.", 200),
    contactDesignation: required("Enter the contact's designation.", 120),
    contactEmail: z.email('Enter a valid e-mail address.'),
    contactDial: z.string(),
    contactPhone: required('Enter a phone number.', 30),
    altEmail: email,
    altDial: z.string(),
    altPhone: text(30),
    accountManagerId: z.string().min(1, 'Choose an Account Manager.'),
    contractStart: z.string().min(1, 'Choose the contract start date.'),
    contractEnd: z.string().min(1, 'Choose the contract end date.'),
    contractValue: z
      .string()
      .trim()
      .regex(/^(\d+(\.\d{1,2})?)?$/, 'Enter an amount, e.g. 500000.'),
    paymentTerms: z.string(),
    contractNotes: text(250),
    confirmDifferentBusiness: z.boolean(),
  })
  .refine((v) => !v.contractStart || !v.contractEnd || v.contractEnd >= v.contractStart, {
    path: ['contractEnd'],
    message: 'The end date must be on or after the start date.',
  });
export type ClientFormValues = z.infer<typeof clientFormSchema>;

export const emptyClientForm: ClientFormValues = {
  name: '',
  website: '',
  industry: '',
  businessType: '',
  companySize: '',
  country: 'IN',
  description: '',
  contactName: '',
  contactDesignation: '',
  contactEmail: '',
  contactDial: '+91',
  contactPhone: '',
  altEmail: '',
  altDial: '+91',
  altPhone: '',
  accountManagerId: '',
  contractStart: '',
  contractEnd: '',
  contractValue: '',
  paymentTerms: 'monthly',
  contractNotes: '',
  confirmDifferentBusiness: false,
};

function splitPhone(phone: string | null): [string, string] {
  if (!phone) return ['+91', ''];
  const [first, ...rest] = phone.trim().split(/\s+/);
  return first?.startsWith('+') ? [first, rest.join(' ')] : ['+91', phone];
}

export function fromClient(client: ClientDetail): ClientFormValues {
  const [contactDial, contactPhone] = splitPhone(client.contact_phone);
  const [altDial, altPhone] = splitPhone(client.contact_alt_phone);
  return {
    name: client.name,
    website: client.website ?? '',
    industry: client.industry ?? '',
    businessType: client.business_type ?? '',
    companySize: client.company_size ?? '',
    country: client.country ?? 'IN',
    description: client.description ?? '',
    contactName: client.contact_name ?? '',
    contactDesignation: client.contact_designation ?? '',
    contactEmail: client.contact_email ?? '',
    contactDial,
    contactPhone,
    altEmail: client.contact_alt_email ?? '',
    altDial,
    altPhone,
    accountManagerId: client.account_manager.id,
    contractStart: client.contract_start ?? '',
    contractEnd: client.contract_end ?? '',
    contractValue: client.contract_value ? String(Number(client.contract_value)) : '',
    paymentTerms: client.payment_terms ?? '',
    contractNotes: client.contract_notes ?? '',
    confirmDifferentBusiness: false,
  };
}

/** Form values → API body (blank strings become null). */
export function toClientBody(v: ClientFormValues): Omit<ClientCreate, 'services'> {
  const blank = (s: string) => (s.trim() === '' ? null : s.trim());
  const phone = (dial: string, number: string) =>
    number.trim() ? `${dial} ${number.trim()}` : null;
  return {
    name: v.name.trim(),
    website: blank(v.website),
    industry: v.industry.trim(),
    business_type: (blank(v.businessType) as ClientCreate['business_type']) ?? null,
    company_size: (blank(v.companySize) as ClientCreate['company_size']) ?? null,
    country: v.country,
    description: blank(v.description),
    contact_name: v.contactName.trim(),
    contact_designation: v.contactDesignation.trim(),
    contact_email: v.contactEmail.trim(),
    contact_phone: phone(v.contactDial, v.contactPhone) ?? '',
    contact_alt_email: blank(v.altEmail),
    contact_alt_phone: phone(v.altDial, v.altPhone),
    contract_start: v.contractStart,
    contract_end: v.contractEnd,
    contract_value: blank(v.contractValue),
    payment_terms: (blank(v.paymentTerms) as ClientCreate['payment_terms']) ?? null,
    contract_notes: blank(v.contractNotes),
    account_manager_id: v.accountManagerId,
    confirm_different_business: v.confirmDifferentBusiness,
  };
}

function Section({
  icon: Icon,
  title,
  children,
  className,
}: {
  icon: typeof Building2;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('flex flex-col gap-4', className)}>
      <h2 className="flex items-center gap-3 text-base font-semibold">
        <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent">
          <Icon aria-hidden className="size-[18px]" />
        </span>
        {title}
      </h2>
      {children}
    </section>
  );
}

const MAX_CONTRACT = 10 * 1024 * 1024;

export interface ClientFormProps {
  formId: string;
  defaultValues: ClientFormValues;
  /** Create only: let the user attach the signed contract (uploaded after save). */
  withUpload?: boolean;
  /** Create only: the services the client bought (at least one). */
  withServices?: boolean;
  onSubmit(
    values: ClientFormValues,
    contract: File | null,
    services: ServiceSelection[],
  ): Promise<void>;
  onBusyChange?(busy: boolean): void;
}

export function ClientForm({
  formId,
  defaultValues,
  withUpload,
  withServices,
  onSubmit,
  onBusyChange,
}: ClientFormProps) {
  const managers = useAccountManagers();
  const { actor } = useAuth();
  const [choice, setChoice] = useState<ServiceChoice>({});
  const [servicesError, setServicesError] = useState<string | undefined>();
  const dupId = useId();
  const fileId = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const [contract, setContract] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const {
    register,
    handleSubmit,
    setError,
    setValue,
    getValues,
    watch,
    formState: { errors },
  } = useForm<ClientFormValues>({ resolver: zodResolver(clientFormSchema), defaultValues });

  // The manager options arrive after the form mounts: re-apply the chosen value so
  // the <select> shows it (an uncontrolled select can't select a missing option).
  useEffect(() => {
    if (managers.data) setValue('accountManagerId', getValues('accountManagerId'));
  }, [managers.data, setValue, getValues]);

  const submit = handleSubmit(async (values) => {
    if (withServices) {
      const bad = Object.values(choice).some(
        (fee) => fee.trim() && !/^\d+(\.\d{1,2})?$/.test(fee.trim()),
      );
      if (!Object.keys(choice).length || bad) {
        setServicesError(
          bad ? 'Enter fees as amounts, e.g. 45000.' : 'Choose at least one service.',
        );
        document.getElementById('client-services')?.scrollIntoView({ behavior: 'smooth' });
        return;
      }
      setServicesError(undefined);
    }
    onBusyChange?.(true);
    try {
      await onSubmit(values, contract, withServices ? toSelections(choice) : []);
    } catch (error) {
      setError('root', {
        type: error instanceof ApiError ? String(error.details.reason ?? error.code) : 'unknown',
        message: error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
      });
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
      onBusyChange?.(false);
    }
  });

  const pick = (file: File | undefined) => {
    if (!file) return;
    const ok = /\.(pdf|docx?)$/i.test(file.name);
    if (!ok) return setFileError('Upload a PDF, DOC or DOCX file.');
    if (file.size > MAX_CONTRACT) return setFileError('The file is larger than 10 MB.');
    setFileError(null);
    setContract(file);
  };

  const similarName = errors.root?.type === 'similar_name';
  const managerId = watch('accountManagerId');
  const manager = managers.data?.find((m) => m.id === managerId);
  const industry = watch('industry');
  const industries =
    INDUSTRIES.includes(industry) || !industry ? INDUSTRIES : [industry, ...INDUSTRIES];
  const options = (list: readonly string[]) => list.map((v) => ({ value: v, label: v }));
  const dial = DIAL_CODES.map((d) => ({ value: d, label: d }));

  return (
    <form id={formId} onSubmit={submit} noValidate className="flex flex-col gap-4">
      {errors.root?.message ? (
        <Alert
          tone={similarName ? 'warn' : 'bad'}
          title={similarName ? 'Possible duplicate' : undefined}
        >
          {errors.root.message}
        </Alert>
      ) : null}
      <Card className="grid gap-8 p-6 lg:grid-cols-[minmax(0,1.45fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-8">
          <Section icon={Building2} title="Company Information">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Company Name *"
                error={errors.name?.message}
                {...register('name')}
              />
              <TextField
                label="Website"
                placeholder="www.example.com"
                error={errors.website?.message}
                {...register('website')}
              />
              <SelectField
                label="Industry *"
                placeholder="Choose…"
                options={options(industries)}
                error={errors.industry?.message}
                {...register('industry')}
              />
              <SelectField
                label="Business Type"
                placeholder="Choose…"
                options={BUSINESS_TYPES}
                {...register('businessType')}
              />
              <SelectField
                label="Company Size"
                placeholder="Choose…"
                options={COMPANY_SIZES}
                {...register('companySize')}
              />
              <SelectField
                label="Country *"
                options={COUNTRY_OPTIONS}
                error={errors.country?.message}
                {...register('country')}
              />
            </div>
            <TextAreaField
              label="Company Description"
              maxLength={500}
              count={watch('description').length}
              error={errors.description?.message}
              {...register('description')}
            />
          </Section>
          <div className="border-t border-line-soft" />
          <Section icon={UserRound} title="Primary Contact">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                label="Contact Name *"
                error={errors.contactName?.message}
                {...register('contactName')}
              />
              <TextField
                label="Designation *"
                error={errors.contactDesignation?.message}
                {...register('contactDesignation')}
              />
              <TextField
                label="Email *"
                type="email"
                error={errors.contactEmail?.message}
                {...register('contactEmail')}
              />
              <div className="grid grid-cols-[92px_1fr] items-start gap-2">
                <SelectField label="Code" options={dial} {...register('contactDial')} />
                <TextField
                  label="Phone *"
                  type="tel"
                  error={errors.contactPhone?.message}
                  {...register('contactPhone')}
                />
              </div>
              <TextField
                label="Alternate Email"
                type="email"
                placeholder="Enter alternate email (optional)"
                error={errors.altEmail?.message}
                {...register('altEmail')}
              />
              <div className="grid grid-cols-[92px_1fr] items-start gap-2">
                <SelectField label="Code " options={dial} {...register('altDial')} />
                <TextField
                  label="Alternate Phone"
                  type="tel"
                  placeholder="Enter alternate phone (optional)"
                  error={errors.altPhone?.message}
                  {...register('altPhone')}
                />
              </div>
            </div>
          </Section>
        </div>

        <div className="flex flex-col gap-8 lg:border-l lg:border-line-soft lg:pl-8">
          <Section icon={UserRoundCog} title="Account Manager">
            <SelectField
              label="Account Manager *"
              placeholder={managers.isPending ? 'Loading…' : 'Choose…'}
              options={(managers.data ?? []).map((m) => ({ value: m.id, label: m.full_name }))}
              error={errors.accountManagerId?.message}
              {...register('accountManagerId')}
            />
            {manager ? (
              <div className="flex items-center gap-3 rounded-lg border border-line px-3 py-2.5">
                <Avatar name={manager.full_name} size="sm" />
                <div>
                  <div className="text-sm font-medium">{manager.full_name}</div>
                  <div className="text-xs text-muted">{manager.email}</div>
                </div>
              </div>
            ) : null}
          </Section>
          <Section icon={FileText} title="Contract Details">
            <TextField
              label="Contract Start Date *"
              type="date"
              error={errors.contractStart?.message}
              {...register('contractStart')}
            />
            <TextField
              label="Contract End Date *"
              type="date"
              error={errors.contractEnd?.message}
              {...register('contractEnd')}
            />
            <TextField
              label="Contract Value (INR)"
              inputMode="decimal"
              placeholder="₹ 5,00,000"
              error={errors.contractValue?.message}
              {...register('contractValue')}
            />
            <SelectField
              label="Payment Terms"
              placeholder="Choose…"
              options={PAYMENT_TERMS}
              {...register('paymentTerms')}
            />
            <TextAreaField
              label="Notes"
              maxLength={250}
              count={watch('contractNotes').length}
              error={errors.contractNotes?.message}
              {...register('contractNotes')}
            />
            {withUpload ? (
              <div className="label">
                <span>
                  Upload Contract <span className="font-normal text-muted">(Optional)</span>
                </span>
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setDragging(false);
                    pick(e.dataTransfer.files[0]);
                  }}
                  className={cn(
                    'flex flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-6 text-center font-normal',
                    dragging
                      ? 'border-accent bg-accent-soft'
                      : 'border-accent/40 bg-accent-soft/30',
                  )}
                >
                  <Upload aria-hidden className="size-6 text-accent" />
                  {contract ? (
                    <span className="text-sm text-fg">
                      {contract.name}{' '}
                      <span className="text-muted">({formatBytes(contract.size)})</span>{' '}
                      <button type="button" className="link" onClick={() => setContract(null)}>
                        Remove
                      </button>
                    </span>
                  ) : (
                    <span className="text-sm text-fg">
                      Drag &amp; drop file here or{' '}
                      <button
                        type="button"
                        className="link underline"
                        onClick={() => fileInput.current?.click()}
                      >
                        browse
                      </button>
                    </span>
                  )}
                  <span className="text-xs text-muted">PDF, DOC, DOCX (Max. 10MB)</span>
                  <input
                    id={fileId}
                    ref={fileInput}
                    type="file"
                    accept=".pdf,.doc,.docx"
                    aria-label="Contract file"
                    className="sr-only"
                    onChange={(e) => pick(e.target.files?.[0])}
                  />
                </div>
                {fileError ? (
                  <span className="text-[12.5px] font-normal text-bad">{fileError}</span>
                ) : null}
              </div>
            ) : null}
          </Section>
        </div>
      </Card>
      {withServices ? (
        <Card className="p-6" id="client-services">
          <Section icon={Briefcase} title="Services *">
            <ServicePicker
              value={choice}
              onChange={(next) => {
                setChoice(next);
                setServicesError(undefined);
              }}
              showFees={can(actor?.permissions ?? [], P.financeView)}
              error={servicesError}
            />
          </Section>
        </Card>
      ) : null}
      <label
        htmlFor={dupId}
        className={cn(
          'flex items-center gap-2 text-[13px]',
          similarName && 'font-medium text-warn',
        )}
      >
        <input id={dupId} type="checkbox" {...register('confirmDifferentBusiness')} />
        This is a different business (override a possible-duplicate warning)
      </label>
    </form>
  );
}
