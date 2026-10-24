/**
 * Reporting relationships for one employee (Organization brief §6, §7, §9): edit the
 * explicit lines, preview the impact (validation + chart), then save with an
 * effective date. Lines removed are ended on that date and kept in the history.
 * `org.projects.assign` alone edits Project Manager lines only.
 */
import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useId, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { useToast } from '@/components/ui/Toast';
import {
  REPORTING_KINDS,
  useEmployees,
  usePreviewReporting,
  useProjectOptions,
  useReporting,
  useSaveReporting,
  type Reporting,
  type ReportingKind,
  type ReportingPreview,
} from '@/features/team/api';
import { errorMessage } from '@/features/team/org/DepartmentsTab';
import { OrgChartView } from '@/features/team/org/OrgChartView';
import { LineLegend, LineSample, RelationList } from '@/features/team/org/Relations';
import { formatDate } from '@/lib/format';

interface Draft {
  key: number;
  kind: ReportingKind;
  manager_id: string;
  project_id: string;
}

let nextKey = 1;
const toDraft = (reporting: Reporting): Draft[] =>
  reporting.lines.map((line) => ({
    key: nextKey++,
    kind: line.kind,
    manager_id: line.manager.id,
    project_id: line.project?.id ?? '',
  }));

function today() {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function Editor({ reporting }: { reporting: Reporting }) {
  const employeeId = reporting.employee.id;
  const people = useEmployees();
  const projects = useProjectOptions(true);
  const previewMutation = usePreviewReporting(employeeId);
  const save = useSaveReporting(employeeId);
  const { toast } = useToast();
  const dateId = useId();
  const [draft, setDraft] = useState<Draft[]>(() => toDraft(reporting));
  const [effectiveOn, setEffectiveOn] = useState(today());
  const [preview, setPreview] = useState<{ result: ReportingPreview; signature: string } | null>(
    null,
  );
  const locked = (kind: ReportingKind) => reporting.projects_only && kind !== 'project_manager';
  const body = {
    lines: draft
      .filter((d) => d.manager_id)
      .map((d) => ({
        kind: d.kind,
        manager_id: d.manager_id,
        project_id: d.kind === 'project_manager' && d.project_id ? d.project_id : null,
      })),
    effective_on: effectiveOn || null,
  };
  const signature = JSON.stringify(body);
  const previewed = preview?.signature === signature ? preview.result : null;
  const others = (people.data ?? []).filter((p) => p.id !== employeeId);

  const update = (key: number, patch: Partial<Draft>) =>
    setDraft((rows) => rows.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  async function runPreview() {
    try {
      const result = await previewMutation.mutateAsync(body);
      setPreview({ result, signature });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  async function runSave() {
    try {
      const saved = await save.mutateAsync(body);
      setDraft(toDraft(saved));
      setPreview(null);
      toast({ title: `Reporting for ${reporting.employee.full_name} saved.` });
    } catch (error) {
      toast({ title: errorMessage(error), tone: 'error' });
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid items-start gap-4 xl:grid-cols-[3fr_2fr]">
        <Panel
          title={`Edit relationships: ${reporting.employee.full_name}`}
          description={
            reporting.projects_only
              ? 'You can change Project Manager assignments only.'
              : 'Explicit lines override department defaults. Removing a line ends it on the effective date.'
          }
        >
          {draft.length ? (
            <ul className="flex flex-col gap-2" data-testid="reporting-lines">
              {draft.map((row, index) => (
                <li
                  key={row.key}
                  className="grid grid-cols-1 items-end gap-2 rounded-lg border border-line p-2.5 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto]"
                >
                  <div className="label">
                    <label htmlFor={`kind-${row.key}`}>Relationship {index + 1}</label>
                    <select
                      id={`kind-${row.key}`}
                      className="input"
                      value={row.kind}
                      disabled={locked(row.kind)}
                      onChange={(e) =>
                        update(row.key, { kind: e.target.value as ReportingKind, project_id: '' })
                      }
                    >
                      {REPORTING_KINDS.filter((k) => !locked(k.value) || k.value === row.kind).map(
                        (k) => (
                          <option key={k.value} value={k.value}>
                            {k.label}
                          </option>
                        ),
                      )}
                    </select>
                  </div>
                  <div className="label">
                    <label htmlFor={`manager-${row.key}`}>Reports to</label>
                    <select
                      id={`manager-${row.key}`}
                      className="input"
                      value={row.manager_id}
                      disabled={locked(row.kind)}
                      onChange={(e) => update(row.key, { manager_id: e.target.value })}
                    >
                      <option value="">Choose a person…</option>
                      {others.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.full_name} ({p.designation?.name ?? p.code})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="label">
                    <label htmlFor={`project-${row.key}`}>Project</label>
                    <select
                      id={`project-${row.key}`}
                      className="input"
                      value={row.project_id}
                      disabled={row.kind !== 'project_manager'}
                      onChange={(e) => update(row.key, { project_id: e.target.value })}
                    >
                      <option value="">
                        {row.kind === 'project_manager' ? 'All delivery (no project)' : '—'}
                      </option>
                      {projects.data?.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.code} · {p.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Remove relationship ${index + 1}`}
                    disabled={locked(row.kind)}
                    onClick={() => setDraft((rows) => rows.filter((r) => r.key !== row.key))}
                  >
                    <Trash2 size={15} />
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted">No explicit lines: only department defaults apply.</p>
          )}
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <Button
              size="sm"
              onClick={() =>
                setDraft((rows) => [
                  ...rows,
                  {
                    key: nextKey++,
                    kind: reporting.projects_only ? 'project_manager' : 'functional_manager',
                    manager_id: '',
                    project_id: '',
                  },
                ])
              }
            >
              <Plus size={15} /> Add relationship
            </Button>
            <div className="label">
              <label htmlFor={dateId}>Effective from</label>
              <input
                id={dateId}
                type="date"
                className="input"
                max={today()}
                value={effectiveOn}
                onChange={(e) => setEffectiveOn(e.target.value)}
              />
            </div>
            <div className="ml-auto flex gap-2">
              <Button onClick={() => void runPreview()} disabled={previewMutation.isPending}>
                Preview changes
              </Button>
              <Button
                variant="primary"
                disabled={!previewed?.valid || save.isPending}
                title={previewed ? undefined : 'Preview the changes first'}
                onClick={() => void runSave()}
              >
                Save changes
              </Button>
            </div>
          </div>
        </Panel>
        <Panel title="What applies now" description="Explicit lines plus department defaults.">
          <RelationList relations={reporting.effective} />
          <div className="mt-3">
            <LineLegend />
          </div>
        </Panel>
      </div>

      {previewed ? (
        <Panel title="Preview" description="Nothing is saved until you choose Save changes.">
          {previewed.errors.length ? (
            <Alert tone="bad" title="These changes can't be saved">
              <ul className="list-disc pl-4">
                {previewed.errors.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            </Alert>
          ) : (
            <div className="flex flex-col gap-4" data-testid="reporting-preview">
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <h3 className="mb-1 text-[13px] font-semibold">Starting</h3>
                  {previewed.added.length ? (
                    <ul className="flex flex-col gap-1 text-[13px]">
                      {previewed.added.map((c) => (
                        <li key={`${c.kind}-${c.manager.id}-${c.project?.id ?? ''}`}>
                          <Badge tone="ok">+</Badge> {c.kind_label}: {c.manager.full_name}
                          {c.project ? ` (${c.project.name})` : ''}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-muted">Nothing new.</p>
                  )}
                </div>
                <div>
                  <h3 className="mb-1 text-[13px] font-semibold">Ending</h3>
                  {previewed.ended.length ? (
                    <ul className="flex flex-col gap-1 text-[13px]">
                      {previewed.ended.map((c) => (
                        <li key={`${c.kind}-${c.manager.id}-${c.project?.id ?? ''}`}>
                          <Badge tone="bad">−</Badge> {c.kind_label}: {c.manager.full_name}
                          {c.project ? ` (${c.project.name})` : ''}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[13px] text-muted">Nothing ends.</p>
                  )}
                </div>
                <div>
                  <h3 className="mb-1 text-[13px] font-semibold">Will apply</h3>
                  <RelationList relations={previewed.effective} compact />
                </div>
              </div>
              <OrgChartView chart={previewed.chart} preview />
            </div>
          )}
        </Panel>
      ) : null}

      <Panel
        title="History"
        description="Every relationship ever recorded. Ended lines are kept."
        flush
      >
        {reporting.history.length ? (
          <div className="overflow-x-auto">
            <table className="table" data-testid="reporting-history">
              <thead>
                <tr>
                  <th>Relationship</th>
                  <th>Reports to</th>
                  <th>From</th>
                  <th>Until</th>
                  <th>Changed by</th>
                </tr>
              </thead>
              <tbody>
                {reporting.history.map((line) => (
                  <tr key={line.id}>
                    <td>
                      <span className="flex items-center gap-1.5">
                        <LineSample kind={line.kind} /> {line.kind_label}
                        {line.project ? <Badge tone="info">{line.project.name}</Badge> : null}
                      </span>
                    </td>
                    <td>{line.manager.full_name}</td>
                    <td>{formatDate(line.starts_on)}</td>
                    <td>
                      {line.ends_on ? formatDate(line.ends_on) : <Badge tone="ok">Active</Badge>}
                    </td>
                    <td className="text-muted">
                      {[line.created_by, line.ended_by].filter(Boolean).join(' → ') || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No reporting lines recorded yet" />
        )}
      </Panel>
    </div>
  );
}

export function ReportingEditor() {
  const [params, setParams] = useSearchParams();
  const people = useEmployees();
  const selected = params.get('employee');
  const reporting = useReporting(selected);
  const pickerId = useId();
  const sorted = useMemo(() => people.data ?? [], [people.data]);

  // Keep the URL valid when the chosen employee disappears (e.g. exited).
  useEffect(() => {
    if (selected && people.data && !people.data.some((p) => p.id === selected)) {
      setParams((current) => {
        const next = new URLSearchParams(current);
        next.delete('employee');
        return next;
      });
    }
  }, [selected, people.data, setParams]);

  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <div className="label max-w-md">
          <label htmlFor={pickerId}>Employee</label>
          <select
            id={pickerId}
            className="input"
            value={selected ?? ''}
            onChange={(e) =>
              setParams((current) => {
                const next = new URLSearchParams(current);
                if (e.target.value) next.set('employee', e.target.value);
                else next.delete('employee');
                return next;
              })
            }
          >
            <option value="">Choose an employee…</option>
            {sorted.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name} · {p.department?.name ?? 'No department'}
              </option>
            ))}
          </select>
        </div>
      </Panel>
      {!selected ? (
        <Panel flush>
          <EmptyState
            title="Choose an employee"
            description="Edit their direct, functional and project reporting, approvers and escalation contacts."
          />
        </Panel>
      ) : reporting.data ? (
        <Editor key={reporting.data.employee.id} reporting={reporting.data} />
      ) : (
        <EmptyState title="Loading…" />
      )}
    </div>
  );
}
