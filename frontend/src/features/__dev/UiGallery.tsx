/**
 * /__dev/ui: every primitive on one page (dev builds only). Sample content is
 * generic placeholder text, not business data.
 */
import { useState, type ReactNode } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Panel, StatCard } from '@/components/ui/Card';
import { KeyValue, Progress, StepList, Tabs, Timeline } from '@/components/ui/Data';
import { Dialog, Drawer } from '@/components/ui/Dialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/ui/PageHeader';
import { useToast } from '@/components/ui/Toast';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-xs font-semibold tracking-[.06em] text-muted uppercase">{title}</h3>
      <div className="flex flex-wrap items-start gap-3">{children}</div>
    </section>
  );
}

type TabKey = 'one' | 'two' | 'three';

export function Component() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [tab, setTab] = useState<TabKey>('one');
  const { toast } = useToast();

  return (
    <div data-testid="ui-gallery" className="flex flex-col gap-8">
      <PageHeader
        crumb={{ label: 'Dashboard', to: '/dashboard' }}
        title="UI primitives"
        description="Dev-only gallery of the provisional primitives (look from the clickable demo)."
        actions={<Button variant="primary">Primary action</Button>}
      />

      <Section title="Button">
        <Button variant="primary">Primary</Button>
        <Button>Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
        <Button size="sm">Small</Button>
        <Button disabled>Disabled</Button>
        <LinkButton to="/dashboard">LinkButton</LinkButton>
      </Section>

      <Section title="Badge">
        <Badge>Neutral</Badge>
        <Badge tone="accent">Accent</Badge>
        <Badge tone="ok">Ok</Badge>
        <Badge tone="warn">Warn</Badge>
        <Badge tone="bad">Bad</Badge>
        <Badge tone="info">Info</Badge>
      </Section>

      <Section title="Stat cards">
        <div className="grid w-full grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-4">
          <StatCard label="Label" value="12" hint="Hint text" />
          <StatCard label="Alerting" value="3" hint="Shown in red when > 0" alert />
          <StatCard label="Money" value="$2,500.00" />
          <StatCard label="Percent" value="40%" />
        </div>
      </Section>

      <Section title="Panel, table, progress">
        <Panel
          className="w-full"
          title="Panel title"
          description="Panel description"
          actions={<Button size="sm">Action</Button>}
          flush
        >
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Count</th>
                </tr>
              </thead>
              <tbody>
                {[0, 40, 100].map((value) => (
                  <tr key={value}>
                    <td>
                      <button type="button" className="link">
                        Row {value}
                      </button>
                      <div className="code">CODE-{value}</div>
                    </td>
                    <td>
                      <Badge tone={value === 100 ? 'ok' : 'accent'}>
                        {value === 100 ? 'Done' : 'Open'}
                      </Badge>
                    </td>
                    <td className="w-[200px]">
                      <Progress value={value} />
                    </td>
                    <td className="font-mono tabular-nums">{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </Section>

      <Section title="Alert (callout)">
        <Alert title="Info">Informational message.</Alert>
        <Alert tone="ok" title="Ok">
          Done.
        </Alert>
        <Alert tone="warn" title="Warn">
          Check this.
        </Alert>
        <Alert tone="bad" title="Bad">
          Something failed.
        </Alert>
      </Section>

      <Section title="Tabs, steps, key/value, timeline">
        <div className="w-full">
          <Tabs<TabKey>
            label="Sample tabs"
            value={tab}
            onChange={setTab}
            items={[
              { key: 'one', label: 'One' },
              { key: 'two', label: 'Two' },
              { key: 'three', label: 'Three' },
            ]}
          />
          <div className="grid gap-4 md:grid-cols-3">
            <Panel>
              <StepList
                steps={[
                  { label: 'Done step', state: 'done' },
                  { label: 'Step in progress', state: 'progress', detail: 'Detail line' },
                  { label: 'Blocked step', state: 'blocked', detail: 'Why it is blocked' },
                  { label: 'Not started', state: 'todo' },
                ]}
              />
            </Panel>
            <Panel>
              <KeyValue
                items={[
                  ['Label', 'Value'],
                  ['Code', <span className="code">CODE-0001</span>],
                  ['Empty', null],
                ]}
              />
            </Panel>
            <Panel>
              <Timeline
                entries={[
                  { id: '1', text: 'Something happened', meta: 'Someone · 16 Oct, 14:05' },
                  { id: '2', text: 'Something else happened', meta: 'Someone · 16 Oct, 13:40' },
                ]}
              />
            </Panel>
          </div>
        </div>
      </Section>

      <Section title="Empty state">
        <Panel className="w-96" flush>
          <EmptyState
            title="Nothing here"
            description="Description line."
            action={<Button size="sm">Action</Button>}
          />
        </Panel>
      </Section>

      <Section title="Dialog, drawer, toast">
        <Button onClick={() => setDialogOpen(true)}>Open dialog</Button>
        <Button onClick={() => setDrawerOpen(true)}>Open drawer</Button>
        <Button onClick={() => toast({ title: 'Saved' })}>Toast</Button>
        <Button onClick={() => toast({ title: 'Could not save', tone: 'error' })}>
          Error toast
        </Button>
        <Dialog
          open={dialogOpen}
          onClose={() => setDialogOpen(false)}
          title="Dialog title"
          footer={<Button onClick={() => setDialogOpen(false)}>Close</Button>}
        >
          Dialog body
        </Dialog>
        <Drawer
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          eyebrow="CODE-1 · Context"
          title="Drawer title"
          footer={<Button variant="primary">Primary</Button>}
        >
          <KeyValue items={[['Label', 'Value']]} />
        </Drawer>
      </Section>

      <Section title="Form controls">
        <form className="grid w-full grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
          <label className="label" htmlFor="g-text">
            Text
            <input id="g-text" className="input" placeholder="Placeholder" />
          </label>
          <label className="label" htmlFor="g-select">
            Select
            <select id="g-select" className="input">
              <option>Option</option>
            </select>
          </label>
          <label className="label" htmlFor="g-date">
            Date
            <input id="g-date" className="input" type="date" />
          </label>
        </form>
      </Section>
    </div>
  );
}
