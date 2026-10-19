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
        description="The employee ID (DD-0001…) is assigned automatically. Personal details are added from the profile, by the employee or HR."
      />
      <Panel>
        <EmploymentForm
          initial={emptyEmployment}
          submitLabel="Create employee"
          cancelTo="/team/employees"
          onSubmit={async (values) => {
            try {
              const body = toBody(values);
              const employee = await create.mutateAsync({
                ...body,
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
