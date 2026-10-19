/**
 * Screen 8 – Internal Team (product spec): assigned members with their role on the
 * account, service area, responsibilities and time allocation, plus coverage of the
 * service areas the engagement needs.
 */
import { CircleAlert, CircleCheck, Plus, UsersRound } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';

import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, Panel } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Data';
import { Dialog } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { TextField } from '@/components/ui/Field';
import { SelectField, TextAreaField } from '@/components/ui/Fields';
import { Menu } from '@/components/ui/Menu';
import { useToast } from '@/components/ui/Toast';
import {
  AREAS,
  onboardingApi,
  useOnboarding,
  useOnboardingAction,
  useTeamOptions,
  type TeamArea,
  type TeamMember,
} from '@/features/onboarding/api';
import { ApiError } from '@/lib/api-client';

function MemberDialog({
  clientId,
  member,
  onClose,
}: {
  clientId: string;
  member: TeamMember | null;
  onClose(): void;
}) {
  const action = useOnboardingAction(clientId);
  const options = useTeamOptions(clientId, member === null);
  const { toast } = useToast();
  const formId = useId();
  const [userId, setUserId] = useState('');
  const [area, setArea] = useState<TeamArea | ''>(member?.area ?? '');
  const [roleTitle, setRoleTitle] = useState(member?.role_title ?? '');
  const [responsibilities, setResponsibilities] = useState(member?.responsibilities ?? '');
  const [allocation, setAllocation] = useState(member?.allocation?.toString() ?? '');

  async function submit(event: FormEvent) {
    event.preventDefault();
    const body = {
      area: area || null,
      role_title: roleTitle || null,
      responsibilities: responsibilities || null,
      allocation: allocation ? Number(allocation) : null,
    };
    try {
      await action.mutateAsync(() =>
        member
          ? onboardingApi.updateTeamMember(clientId, member.user.id, body)
          : onboardingApi.addTeamMember(clientId, { user_id: userId, ...body }),
      );
      toast({ title: member ? 'Team member updated.' : 'Team member assigned.' });
      onClose();
    } catch (error) {
      toast({
        title: error instanceof ApiError ? error.message : 'Something went wrong.',
        tone: 'error',
      });
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={member ? `Edit ${member.user.full_name}` : 'Assign team member'}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form={formId} variant="primary" disabled={action.isPending}>
            {member ? 'Save' : 'Assign'}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
        {!member ? (
          <div className="sm:col-span-2">
            <SelectField
              label="Team member *"
              required
              placeholder={options.isPending ? 'Loading…' : 'Choose a person…'}
              options={(options.data ?? []).map((u) => ({ value: u.id, label: u.full_name }))}
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
          </div>
        ) : null}
        <SelectField
          label="Service area"
          placeholder="Choose…"
          options={AREAS}
          value={area}
          onChange={(e) => setArea(e.target.value as TeamArea | '')}
        />
        <TextField
          label="Role on this account"
          maxLength={100}
          placeholder="SEO Lead"
          value={roleTitle}
          onChange={(e) => setRoleTitle(e.target.value)}
        />
        <div className="sm:col-span-2">
          <TextAreaField
            label="Responsibilities"
            maxLength={2000}
            value={responsibilities}
            onChange={(e) => setResponsibilities(e.target.value)}
          />
        </div>
        <TextField
          label="Allocation (% of their time)"
          type="number"
          min={0}
          max={100}
          value={allocation}
          onChange={(e) => setAllocation(e.target.value)}
        />
      </form>
    </Dialog>
  );
}

export function TeamTab({ clientId }: { clientId: string }) {
  const onboarding = useOnboarding(clientId);
  const action = useOnboardingAction(clientId);
  const { toast } = useToast();
  const [dialog, setDialog] = useState<{ member: TeamMember | null } | null>(null);
  const data = onboarding.data;
  if (!data) return <EmptyState title="Loading team…" />;
  const owner = data.permissions.owner;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold">Internal Team</h2>
          <p className="mt-1 text-muted">
            Who works on this account, their roles and responsibilities. Team members can see the
            client; the internal kickoff needs at least one.
          </p>
        </div>
        {owner ? (
          <Button variant="primary" onClick={() => setDialog({ member: null })}>
            <Plus aria-hidden className="size-4" />
            Assign Member
          </Button>
        ) : null}
      </div>
      <div className="grid items-start gap-5 xl:grid-cols-[1fr_320px]">
        <Card className="overflow-hidden">
          {data.team.length ? (
            <div className="overflow-x-auto">
              <table className="table" data-testid="team-table">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Role</th>
                    <th>Area</th>
                    <th>Responsibilities</th>
                    <th className="min-w-[140px]">Allocation</th>
                    {owner ? <th className="text-right">Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {data.team.map((member) => (
                    <tr key={member.user.id}>
                      <td>
                        <div className="flex items-center gap-3">
                          <Avatar name={member.user.full_name} size="sm" />
                          <div>
                            <div className="font-medium">{member.user.full_name}</div>
                            <div className="text-xs text-muted">{member.email}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        {member.role_title ?? '—'}
                        {member.role ? (
                          <div className="text-xs text-muted">{member.role}</div>
                        ) : null}
                      </td>
                      <td>
                        {member.area ? (
                          <Badge tone="accent">
                            {AREAS.find((a) => a.value === member.area)?.label}
                          </Badge>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="max-w-72 text-[13px] whitespace-pre-wrap text-muted">
                        {member.responsibilities ?? '—'}
                      </td>
                      <td>
                        {member.allocation !== null ? (
                          <Progress
                            value={member.allocation}
                            label={`${member.user.full_name} allocation`}
                          />
                        ) : (
                          '—'
                        )}
                      </td>
                      {owner ? (
                        <td className="text-right">
                          <Menu
                            label={`Actions for ${member.user.full_name}`}
                            items={[
                              { label: 'Edit role', onSelect: () => setDialog({ member }) },
                              {
                                label: 'Remove from team',
                                danger: true,
                                onSelect: async () => {
                                  try {
                                    await action.mutateAsync(() =>
                                      onboardingApi.removeTeamMember(clientId, member.user.id),
                                    );
                                    toast({
                                      title: `${member.user.full_name} removed from the team.`,
                                    });
                                  } catch (error) {
                                    toast({
                                      title:
                                        error instanceof ApiError
                                          ? error.message
                                          : 'Something went wrong.',
                                      tone: 'error',
                                    });
                                  }
                                },
                              },
                            ]}
                          />
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={UsersRound}
              title="No team assigned"
              description="Assign the specialists who will deliver this account."
            />
          )}
        </Card>
        <Panel title="Coverage" description="Service areas and who covers them">
          <ul className="flex flex-col gap-3" data-testid="coverage">
            {data.coverage
              .filter((c) => c.required || c.members.length)
              .map((c) => (
                <li key={c.area} className="flex items-start gap-3">
                  {c.members.length ? (
                    <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-ok" />
                  ) : (
                    <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-warn" />
                  )}
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{c.label}</div>
                    <div className="text-xs text-muted">
                      {c.members.length
                        ? c.members.map((m) => m.full_name).join(', ')
                        : 'Not covered yet'}
                    </div>
                  </div>
                </li>
              ))}
          </ul>
        </Panel>
      </div>
      {dialog ? (
        <MemberDialog clientId={clientId} member={dialog.member} onClose={() => setDialog(null)} />
      ) : null}
    </div>
  );
}
