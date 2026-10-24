/** /team/employees/new (HR): step 1 of employee onboarding, the employee record. */
import { useNavigate } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Panel } from '@/components/ui/Card';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import { useCreateEmployee, type EmployeeCreate } from '@/features/team/api';
import { EmploymentForm, emptyEmployment, toBody } from '@/features/team/EmploymentForm';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { can, P } from '@/lib/permissions';

const crumb = { label: 'Employees', to: '/team/employees' };

export function Component() {
  const { actor } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();
  const create = useCreateEmployee();
  const placement = can(actor?.permissions ?? [], P.orgReportingManage);

  if (!can(actor?.permissions ?? [], P.hrManage)) {
    return (
      <>
        <PageHeader title="New employee" crumb={crumb} />
        <Alert tone="bad" title="Access denied">
          Only HR can add employees.
        </Alert>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="New employee"
        crumb={crumb}
        description={
          placement
            ? 'The employee ID (DD-0001…) is assigned automatically. Personal details are added from the profile, by the employee or HR.'
            : 'The employee ID (DD-0001…) is assigned automatically. Department, designation and reporting lines are set by an Organization Admin in Organization & Role Settings.'
        }
      />
      <Panel>
        <EmploymentForm
          initial={emptyEmployment}
          placement={placement}
          submitLabel="Create employee"
          cancelTo="/team/employees"
          onSubmit={async (values) => {
            try {
              const body = toBody(values, { placement });
              const employee = await create.mutateAsync({
                ...body,
                full_name: body.full_name ?? '',
                employment_type: values.employment_type,
                status: body.status as EmployeeCreate['status'],
              });
              toast({ title: `${employee.full_name} added (${employee.code}).` });
              navigate(`/team/employees/${employee.id}`);
            } catch (error) {
              toast({
                title:
                  error instanceof ApiError ? error.message : 'Something went wrong. Try again.',
                tone: 'error',
              });
            }
          }}
        />
      </Panel>
    </>
  );
}
