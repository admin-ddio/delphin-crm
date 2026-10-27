/**
 * /services/templates: the task templates of each service. Retainers have setup
 * tasks (first month) and monthly tasks (day of month); projects have delivery
 * phases (offset + duration from the start date). `services.templates.manage` edits;
 * removed tasks are retired, so past months keep their history.
 */
import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Panel } from '@/components/ui/Card';
import { Tabs } from '@/components/ui/Data';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';
import {
  AREA_LABELS,
  useSaveTemplates,
  useServiceTypes,
  useTemplates,
  type TemplateTask,
  type TemplateTaskIn,
} from '@/features/services/api';
import { ApiError } from '@/lib/api-client';

type Phase = TemplateTask['phase'];
type Row = TemplateTaskIn & { key: number };

const PHASES: Record<Phase, { title: string; hint: string }> = {
  setup: {
    title: 'Setup (first month)',
    hint: 'Created when the retainer starts, dated from the start date.',
  },
  monthly: {
    title: 'Every month',
    hint: 'Created each month on the given day; weekends move to Monday.',
  },
  delivery: {
    title: 'Delivery phases',
    hint: 'Created when the project starts, dated from the start date.',
  },
};

let nextKey = 1;
const toRows = (tasks: TemplateTask[]): Row[] =>
  tasks.map((t) => ({
    key: nextKey++,
    id: t.id,
    phase: t.phase,
    title: t.title,
    day_of_month: t.day_of_month,
    start_offset_days: t.start_offset_days,
    duration_days: t.duration_days,
    requires_review: t.requires_review,
    requires_client_approval: t.requires_client_approval,
    area: t.area,
  }));

function Editor({ serviceKey }: { serviceKey: string }) {
  const templates = useTemplates(serviceKey);
  const save = useSaveTemplates(serviceKey);
  const { toast } = useToast();
  const [rows, setRows] = useState<Row[] | null>(null);
  const data = templates.data;
  if (!data) return <EmptyState title="Loading…" />;
  const current = rows ?? toRows(data.tasks);
  const editable = data.can_edit;
  const phases: Phase[] = data.service.kind === 'retainer' ? ['setup', 'monthly'] : ['delivery'];
  const update = (key: number, patch: Partial<Row>) =>
    setRows(current.map((r) => (r.key === key ? { ...r, ...patch } : r)));

  return (
    <div className="flex flex-col gap-4">
      {!editable ? (
        <Alert tone="info">
          You can view these templates. Editing needs the "Edit service task templates" permission.
        </Alert>
      ) : null}
      {phases.map((phase) => {
        const list = current.filter((r) => r.phase === phase);
        return (
          <Panel key={phase} title={PHASES[phase].title} description={PHASES[phase].hint} flush>
            <div className="overflow-x-auto">
              <table className="table" data-testid={`template-${phase}`}>
                <thead>
                  <tr>
                    <th>Task</th>
                    {phase === 'monthly' ? <th>Day</th> : <th>Starts (day)</th>}
                    {phase === 'monthly' ? null : <th>Takes (days)</th>}
                    <th>Area</th>
                    <th>Review</th>
                    <th>Client approval</th>
                    {editable ? <th /> : null}
                  </tr>
                </thead>
                <tbody>
                  {list.map((r, i) => (
                    <tr key={r.key}>
                      <td className="min-w-64">
                        <input
                          className="input"
                          aria-label={`${PHASES[phase].title} task ${i + 1}`}
                          disabled={!editable}
                          maxLength={200}
                          value={r.title}
                          onChange={(e) => update(r.key, { title: e.target.value })}
                        />
                      </td>
                      {phase === 'monthly' ? (
                        <td>
                          <input
                            className="input w-20"
                            type="number"
                            min={1}
                            max={28}
                            aria-label={`Day of month for ${r.title}`}
                            disabled={!editable}
                            value={r.day_of_month ?? 1}
                            onChange={(e) =>
                              update(r.key, { day_of_month: Number(e.target.value) })
                            }
                          />
                        </td>
                      ) : (
                        <>
                          <td>
                            <input
                              className="input w-20"
                              type="number"
                              min={0}
                              aria-label={`Start day for ${r.title}`}
                              disabled={!editable}
                              value={r.start_offset_days ?? 0}
                              onChange={(e) =>
                                update(r.key, { start_offset_days: Number(e.target.value) })
                              }
                            />
                          </td>
                          <td>
                            <input
                              className="input w-20"
                              type="number"
                              min={0}
                              aria-label={`Duration for ${r.title}`}
                              disabled={!editable}
                              value={r.duration_days ?? 0}
                              onChange={(e) =>
                                update(r.key, { duration_days: Number(e.target.value) })
                              }
                            />
                          </td>
                        </>
                      )}
                      <td>
                        <select
                          className="input"
                          aria-label={`Area for ${r.title}`}
                          disabled={!editable}
                          value={r.area ?? ''}
                          onChange={(e) =>
                            update(r.key, { area: (e.target.value || null) as Row['area'] })
                          }
                        >
                          <option value="">Unassigned</option>
                          {Object.entries(AREA_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="text-center">
                        <input
                          type="checkbox"
                          aria-label={`${r.title} needs review`}
                          disabled={!editable}
                          checked={r.requires_review ?? true}
                          onChange={(e) => update(r.key, { requires_review: e.target.checked })}
                        />
                      </td>
                      <td className="text-center">
                        <input
                          type="checkbox"
                          aria-label={`${r.title} needs client approval`}
                          disabled={!editable}
                          checked={r.requires_client_approval ?? false}
                          onChange={(e) =>
                            update(r.key, { requires_client_approval: e.target.checked })
                          }
                        />
                      </td>
                      {editable ? (
                        <td>
                          <Button
                            size="sm"
                            variant="ghost"
                            aria-label={`Remove ${r.title}`}
                            onClick={() => setRows(current.filter((x) => x.key !== r.key))}
                          >
                            <Trash2 size={15} />
                          </Button>
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {editable ? (
              <div className="border-t border-line-soft p-3">
                <Button
                  size="sm"
                  onClick={() =>
                    setRows([
                      ...current,
                      {
                        key: nextKey++,
                        phase,
                        title: 'New task',
                        day_of_month: phase === 'monthly' ? 10 : null,
                        start_offset_days: 0,
                        duration_days: phase === 'monthly' ? 0 : 5,
                        requires_review: true,
                        requires_client_approval: false,
                        area: null,
                      },
                    ])
                  }
                >
                  <Plus size={15} /> Add task
                </Button>
              </div>
            ) : null}
          </Panel>
        );
      })}
      {editable ? (
        <div className="flex gap-2">
          <Button
            variant="primary"
            disabled={!rows || save.isPending}
            onClick={async () => {
              try {
                const saved = await save.mutateAsync(
                  current.map(({ key: _key, ...task }) => ({
                    ...task,
                    day_of_month: task.phase === 'monthly' ? task.day_of_month : null,
                  })),
                );
                setRows(toRows(saved.tasks));
                toast({ title: `${data.service.name} template saved.` });
              } catch (error) {
                toast({
                  title: error instanceof ApiError ? error.message : 'Something went wrong.',
                  tone: 'error',
                });
              }
            }}
          >
            Save template
          </Button>
          <Button disabled={!rows} onClick={() => setRows(null)}>
            Discard changes
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export function Component() {
  const types = useServiceTypes();
  const [params, setParams] = useSearchParams();
  const selected = params.get('service') ?? types.data?.[0]?.key ?? null;
  return (
    <>
      <PageHeader
        crumb={{ label: 'Services & retainers', to: '/services' }}
        title="Service templates"
        description="The tasks each service creates. Changes apply to future months and newly started services."
      />
      {types.data ? (
        <Tabs
          label="Services"
          value={selected ?? ''}
          onChange={(key) => setParams({ service: key })}
          items={types.data.map((t) => ({ key: t.key, label: t.name }))}
        />
      ) : null}
      {selected ? <Editor key={selected} serviceKey={selected} /> : <EmptyState title="Loading…" />}
    </>
  );
}
