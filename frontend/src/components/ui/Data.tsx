/**
 * Data display primitives seen in the clickable demo: Progress, Tabs, StepList,
 * KeyValue, Timeline. PROVISIONAL visuals; replace with verbatim pilot ports.
 */
import { Check } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

// ---------------------------------------------------------------- Progress

export function Progress({ value, label }: { value: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="flex items-center gap-2">
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={label ?? 'Progress'}
        className="h-1.5 min-w-[60px] flex-1 overflow-hidden rounded bg-sunk"
      >
        <i
          className={cn('block h-full', pct === 100 ? 'bg-ok' : 'bg-accent')}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-[34px] text-right font-mono text-[11.5px] font-medium text-muted">
        {pct}%
      </span>
    </div>
  );
}

// ---------------------------------------------------------------- Tabs

export interface TabItem<K extends string> {
  key: K;
  label: ReactNode;
}

export interface TabsProps<K extends string> {
  items: readonly TabItem<K>[];
  value: K;
  onChange(key: K): void;
  label: string;
}

export function Tabs<K extends string>({ items, value, onChange, label }: TabsProps<K>) {
  return (
    <div role="tablist" aria-label={label} className="mb-4 flex gap-0.5 overflow-x-auto border-b border-line">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          role="tab"
          aria-selected={item.key === value}
          onClick={() => onChange(item.key)}
          className={cn(
            '-mb-px cursor-pointer border-b-2 px-3 py-2 font-medium whitespace-nowrap',
            item.key === value ? 'border-accent text-accent-strong' : 'border-transparent text-muted',
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- StepList

export type StepState = 'todo' | 'progress' | 'done' | 'blocked';

export interface StepItem {
  label: string;
  state: StepState;
  detail?: string;
}

export function StepList({ steps }: { steps: readonly StepItem[] }) {
  return (
    <ol className="flex flex-col gap-[7px]">
      {steps.map((step, index) => (
        <li key={step.label} className="grid grid-cols-[20px_1fr] gap-2 text-[13px]">
          <span
            aria-hidden
            className={cn(
              'mt-px grid size-[18px] place-items-center rounded-full border-2 text-[11px]',
              step.state === 'done' && 'border-ok bg-ok text-on-accent',
              step.state === 'progress' && 'border-accent',
              step.state === 'blocked' && 'border-bad text-bad',
              step.state === 'todo' && 'border-line',
            )}
          >
            {step.state === 'done' ? <Check className="size-3" /> : step.state === 'blocked' ? '!' : null}
          </span>
          <span className={step.state === 'done' ? 'text-muted' : undefined}>
            {index + 1}. {step.label}
            <span className="sr-only"> ({step.state})</span>
            {step.state !== 'done' && step.detail ? (
              <small className="block text-[11.5px] text-muted">{step.detail}</small>
            ) : null}
          </span>
        </li>
      ))}
    </ol>
  );
}

// ---------------------------------------------------------------- KeyValue

export function KeyValue({ items }: { items: readonly [label: string, value: ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[140px_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-[13px]">
      {items.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className="m-0">{value ?? '—'}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------- Timeline

export interface TimelineEntry {
  id: string;
  text: ReactNode;
  meta: ReactNode;
}

export function Timeline({ entries }: { entries: readonly TimelineEntry[] }) {
  return (
    <ul className="flex flex-col gap-2.5 border-l border-line pl-3.5">
      {entries.map((entry) => (
        <li
          key={entry.id}
          className="relative text-[13px] before:absolute before:top-1.5 before:-left-[18px] before:size-[7px] before:rounded-full before:bg-accent"
        >
          {entry.text}
          <small className="block text-[11.5px] text-faint">{entry.meta}</small>
        </li>
      ))}
    </ul>
  );
}
