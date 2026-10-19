/**
 * Screen 11 – Onboarding Summary: one printable page with the 13 steps, client and
 * contract, questionnaire highlights, access, KPIs, kickoffs, team and documents.
 */
import { Printer } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, Panel } from '@/components/ui/Card';
import { KeyValue, StepList } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { Ring } from '@/components/ui/Ring';
import { labelOf, PAYMENT_TERMS, type ClientDetail } from '@/features/clients/api';
import {
  ACCESS_STATUS,
  AREAS,
  CHANNELS,
  KPI_STATUS,
  ONBOARDING_STATUS,
  useOnboarding,
} from '@/features/onboarding/api';
import { formatDate, formatDateTime, formatINR } from '@/lib/format';

export function SummaryTab({ client }: { client: ClientDetail }) {
  const onboarding = useOnboarding(client.id);
  const data = onboarding.data;
  if (!data) return <EmptyState title="Loading summary…" />;
  const q = data.questionnaire;
  const a = q.answers;
  const status = ONBOARDING_STATUS[data.status];
  const goals = (a.business_goals?.goals ?? [])
    .map((g) => q.goals.find((x) => x.key === g)?.label)
    .join(', ');
  const tones = (a.brand_voice?.tones ?? [])
    .map((t) => q.tones.find((x) => x.key === t)?.label)
    .join(', ');
  const kick = (k: typeof data.kickoff_client) =>
    k.state === 'done'
      ? `Completed ${k.at ? formatDate(k.at) : ''}`
      : k.state === 'scheduled'
        ? `Scheduled ${k.at ? formatDateTime(k.at) : ''}`
        : 'Not scheduled';

  return (
    <div className="flex flex-col gap-5" data-testid="onboarding-summary">
      <Card className="flex flex-wrap items-center gap-6 p-6">
        <Ring value={data.progress} size={96} label="Onboarding progress" />
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-bold">Onboarding Summary</h2>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-muted">
            <Badge tone={status.tone}>{status.label}</Badge>
            {data.completed_at
              ? `Completed ${formatDate(data.completed_at)}`
              : `Started ${formatDate(data.client.created_at)}`}
            {data.reviewed_at ? ` · Reviewed ${formatDate(data.reviewed_at)}` : ''}
          </p>
        </div>
        <Button onClick={() => window.print()} className="print:hidden">
          <Printer aria-hidden className="size-4" />
          Print / Save as PDF
        </Button>
      </Card>

      <div className="grid items-start gap-5 xl:grid-cols-2">
        <Panel title="Onboarding checklist (13 steps)">
          <StepList
            steps={data.steps.map((s) => ({
              label: s.label,
              state: s.state,
              detail: s.state === 'done' ? undefined : s.detail || s.hint,
            }))}
          />
        </Panel>
        <div className="flex flex-col gap-5">
          <Panel title="Client & contract">
            <KeyValue
              items={[
                ['Client', `${client.name} (${client.code})`],
                ['Account Manager', client.account_manager.full_name],
                [
                  'Primary contact',
                  client.contact_name
                    ? `${client.contact_name} · ${client.contact_email ?? ''}`
                    : null,
                ],
                [
                  'Contract',
                  client.contract_start
                    ? `${formatDate(client.contract_start)} – ${formatDate(client.contract_end)}`
                    : null,
                ],
                ['Value', client.contract_value ? formatINR(client.contract_value) : null],
                ['Payment terms', labelOf(PAYMENT_TERMS, client.payment_terms)],
                ['Documents', `${data.documents} (${data.contract_documents} in Contracts)`],
              ]}
            />
          </Panel>
          <Panel title="Kickoffs & team">
            <KeyValue
              items={[
                ['Client kickoff', kick(data.kickoff_client)],
                ['Internal kickoff', kick(data.kickoff_internal)],
                [
                  'Team',
                  data.team.length
                    ? data.team
                        .map(
                          (t) =>
                            `${t.user.full_name}${t.role_title ? ` (${t.role_title})` : t.area ? ` (${AREAS.find((x) => x.value === t.area)?.label})` : ''}`,
                        )
                        .join(', ')
                    : null,
                ],
              ]}
            />
          </Panel>
        </div>
      </div>

      <Panel
        title="Questionnaire highlights"
        description={
          q.submitted_at ? `Submitted ${formatDateTime(q.submitted_at)}` : 'Not submitted yet'
        }
      >
        <KeyValue
          items={[
            ['Goals', goals || null],
            ['Goals in detail', a.business_goals?.details ?? null],
            ['Target markets', a.target_markets?.locations ?? null],
            ['Audiences', a.target_markets?.audiences ?? null],
            [
              'Competitors',
              (a.competitors?.competitors ?? [])
                .map((c) => c.name)
                .filter(Boolean)
                .join(', ') || null,
            ],
            ['Brand voice', tones || null],
            ['Past SEO work', a.past_seo?.details ?? a.past_seo?.worked_before ?? null],
          ]}
        />
      </Panel>

      <div className="grid items-start gap-5 xl:grid-cols-2">
        <Panel
          title="Access"
          description={`${data.access_summary.verified} of ${data.access_summary.required} verified`}
          flush
        >
          <table className="table">
            <tbody>
              {data.access.map((item) => (
                <tr key={item.key}>
                  <td>{item.label}</td>
                  <td>
                    <Badge tone={ACCESS_STATUS[item.status].tone}>
                      {ACCESS_STATUS[item.status].label}
                    </Badge>
                  </td>
                  <td className="text-muted">{item.verified_by?.full_name ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel
          title="KPI targets"
          description={
            data.kpi_summary.confirmed_by
              ? `Confirmed by ${data.kpi_summary.confirmed_by} via ${CHANNELS.find((c) => c.value === data.kpi_summary.confirmed_via)?.label ?? ''}`
              : 'Awaiting client confirmation'
          }
          flush
        >
          {data.kpis.length ? (
            <table className="table">
              <tbody>
                {data.kpis.map((k) => (
                  <tr key={k.id}>
                    <td>{k.metric}</td>
                    <td className="text-muted whitespace-nowrap">
                      {Number(k.baseline).toLocaleString('en-IN')} →{' '}
                      {Number(k.target).toLocaleString('en-IN')} {k.unit}
                    </td>
                    <td>
                      <Badge tone={KPI_STATUS[k.status].tone}>{KPI_STATUS[k.status].label}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState title="No KPI targets" />
          )}
        </Panel>
      </div>
    </div>
  );
}
