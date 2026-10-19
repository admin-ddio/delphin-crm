/** /onboarding: every visible client's onboarding (layout and wording from the clickable demo). */
import { Badge } from '@/components/ui/Badge';
import { Panel } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { Link } from '@/components/ui/Link';
import { PageHeader } from '@/components/ui/PageHeader';
import { useOnboardingBoard } from '@/features/onboarding/api';
import { ONBOARDING_STATUS } from '@/features/onboarding/api';

export function Component() {
  const board = useOnboardingBoard();
  return (
    <>
      <PageHeader
        title="Client onboarding"
        description="Contract → client → profile → questionnaire → access → verification → KPIs → kickoffs → review → completion → project."
      />
      <Panel flush>
        {board.isPending ? <EmptyState title="Loading…" /> : null}
        {board.isError ? (
          <EmptyState
            title="Couldn't load onboarding"
            description="Reload the page to try again."
          />
        ) : null}
        {board.data?.length === 0 ? (
          <EmptyState title="No onboardings" description="Create a client to start one." />
        ) : null}
        {board.data?.length ? (
          <div className="overflow-x-auto">
            <table className="table" data-testid="onboarding-board">
              <thead>
                <tr>
                  <th>Client</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Current step</th>
                  <th>AM</th>
                </tr>
              </thead>
              <tbody>
                {board.data.map((row) => {
                  const status = ONBOARDING_STATUS[row.status];
                  return (
                    <tr key={row.client_id}>
                      <td>
                        <Link className="link" to={`/clients/${row.client_id}`}>
                          {row.client_name}
                        </Link>
                        <div className="code">{row.client_code}</div>
                      </td>
                      <td>
                        <Badge tone={status.tone}>{status.label}</Badge>
                      </td>
                      <td className="w-[200px]">
                        <Progress
                          value={row.progress}
                          label={`${row.client_name} onboarding progress`}
                        />
                      </td>
                      <td>
                        {row.current_step ?? 'Done'}
                        {row.current_detail ? (
                          <div className="code">{row.current_detail}</div>
                        ) : null}
                      </td>
                      <td>{row.account_manager.full_name}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </>
  );
}
