/** Employment fields (HR): used by /team/employees/new and the profile's Employment tab. */
import { useId, useState, type FormEvent } from 'react';

import { Button, LinkButton } from '@/components/ui/Button';
import {
  EMPLOYEE_STATUS,
  EMPLOYMENT_TYPES,
  WORK_ARRANGEMENTS,
  useDepartments,
  useDesignations,
  useEmployees,
  useUserOptions,
  type EmployeeStatus,
  type EmploymentType,
  type WorkArrangement,
} from '@/features/team/api';

export interface EmploymentValues {
  full_name: string;
  official_email: string;
  department_id: string;
  designation_id: string;
  employment_type: EmploymentType;
  work_arrangement: WorkArrangement | '';
  status: EmployeeStatus;
  joining_date: string;
  manager_id: string;
  leave_approver_id: string;
  user_id: string;
}

export const emptyEmployment: EmploymentValues = {
  full_name: '',
  official_email: '',
  department_id: '',
  designation_id: '',
  employment_type: 'full_time',
  work_arrangement: '',
  status: 'onboarding',
  joining_date: '',
  manager_id: '',
  leave_approver_id: '',
  user_id: '',
};

/** Empty strings become null so the API clears the field. */
export function toBody(values: EmploymentValues) {
  const orNull = (value: string) => value || null;
  return {
    full_name: values.full_name.trim(),
    official_email: orNull(values.official_email.trim()),
    department_id: orNull(values.department_id),
    designation_id: orNull(values.designation_id),
    employment_type: values.employment_type,
    work_arrangement: values.work_arrangement || null,
    status: values.status,
    joining_date: orNull(values.joining_date),
    manager_id: orNull(values.manager_id),
    leave_approver_id: orNull(values.leave_approver_id),
    user_id: orNull(values.user_id),
  };
}

const STATUSES: EmployeeStatus[] = ['onboarding', 'probation', 'active', 'notice', 'on_hold'];

export function EmploymentForm({
  initial,
  employeeId,
  currentAccount,
  submitLabel,
  cancelTo,
  onCancel,
  onSubmit,
}: {
  initial: EmploymentValues;
  /** Set when editing: the employee can't be their own manager or approver. */
  employeeId?: string;
  /** The linked account's label, kept as an option when editing. */
  currentAccount?: { id: string; label: string };
  submitLabel: string;
  cancelTo?: string;
  onCancel?(): void;
  onSubmit(values: EmploymentValues): Promise<void>;
}) {
  const [values, setValues] = useState(initial);
  const [busy, setBusy] = useState(false);
  const departments = useDepartments();
  const designations = useDesignations();
  const people = useEmployees();
  const accounts = useUserOptions(true);
  const id = useId();
  const field = (name: keyof EmploymentValues) => `${id}-${name}`;
  const set = (name: keyof EmploymentValues) => (event: { target: { value: string } }) =>
    setValues((current) => ({ ...current, [name]: event.target.value }));
  const others = (people.data ?? []).filter((p) => p.id !== employeeId);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      await onSubmit(values);
    } finally {
      setBusy(false);
    }
  }

  const select = (
    name: keyof EmploymentValues,
    label: string,
    options: { value: string; label: string }[],
    blank?: string,
  ) => (
    <div className="label">
      <label htmlFor={field(name)}>{label}</label>
      <select id={field(name)} className="input" value={values[name]} onChange={set(name)}>
        {blank !== undefined ? <option value="">{blank}</option> : null}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <form className="flex max-w-3xl flex-col gap-3" onSubmit={submit}>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
        <div className="label">
          <label htmlFor={field('full_name')}>Full legal name *</label>
          <input
            id={field('full_name')}
            className="input"
            required
            maxLength={200}
            value={values.full_name}
            onChange={set('full_name')}
          />
        </div>
        <div className="label">
          <label htmlFor={field('official_email')}>Official e-mail</label>
          <input
            id={field('official_email')}
            type="email"
            className="input"
            value={values.official_email}
            onChange={set('official_email')}
          />
        </div>
        {select(
          'department_id',
          'Department',
          (departments.data ?? [])
            .filter((d) => d.is_active || d.id === initial.department_id)
            .map((d) => ({ value: d.id, label: d.name })),
          'No department',
        )}
        {select(
          'designation_id',
          'Designation',
          (designations.data ?? [])
            .filter((d) => d.is_active || d.id === initial.designation_id)
            .map((d) => ({ value: d.id, label: d.name })),
          'No designation',
        )}
        {select(
          'manager_id',
          'Reporting manager',
          others.map((p) => ({ value: p.id, label: `${p.full_name} (${p.code})` })),
          'No manager',
        )}
        {select(
          'leave_approver_id',
          'Leave approver',
          others.map((p) => ({ value: p.id, label: `${p.full_name} (${p.code})` })),
          'The reporting manager',
        )}
        {select('employment_type', 'Employment type', EMPLOYMENT_TYPES)}
        {select('work_arrangement', 'Work arrangement', WORK_ARRANGEMENTS, 'Not set')}
        {select(
          'status',
          'Employment status',
          (!employeeId
            ? STATUSES.slice(0, 3) // a new record starts onboarding, on probation or active
            : initial.status === 'exited'
              ? [...STATUSES, 'exited' as const]
              : STATUSES
          ).map((s) => ({
            value: s,
            label: EMPLOYEE_STATUS[s].label,
          })),
        )}
        <div className="label">
          <label htmlFor={field('joining_date')}>Joining date</label>
          <input
            id={field('joining_date')}
            type="date"
            className="input"
            value={values.joining_date}
            onChange={set('joining_date')}
          />
        </div>
        {select(
          'user_id',
          'Sign-in account',
          [
            ...(currentAccount ? [{ value: currentAccount.id, label: currentAccount.label }] : []),
            ...(accounts.data ?? []).map((u) => ({
              value: u.id,
              label: `${u.full_name} (${u.email})`,
            })),
          ],
          'Not linked',
        )}
      </div>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={busy}>
          {submitLabel}
        </Button>
        {cancelTo ? <LinkButton to={cancelTo}>Cancel</LinkButton> : null}
        {onCancel ? (
          <Button type="button" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}
