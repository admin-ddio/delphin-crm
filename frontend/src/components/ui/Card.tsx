/** * PROVISIONAL (look from the product owner's mockups, 2026-10-19). Replace with a * verbatim port of the pilot's Card/StatCard. */ import type { LucideIcon } from 'lucide-react';
import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils';

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('card', className)} {...props} />;
}

export interface PanelProps {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** Remove body padding (tables run edge to edge). */
  flush?: boolean;
  /** Icon tile next to the title (mockups). */
  icon?: LucideIcon;
  className?: string;
  children?: ReactNode;
}

/** Card with an optional header (title, description, actions) and a body. */
export function Panel({
  title,
  description,
  actions,
  flush,
  className,
  children,
  icon: Icon,
}: PanelProps) {
  return (
    <section className={cn('card', className)}>
      {title ? (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-5 py-4">
          <div className="flex items-center gap-3">
            {Icon ? (
              <span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent">
                <Icon aria-hidden className="size-[18px]" />
              </span>
            ) : null}
            <div>
              <h2 className="text-[15px] font-semibold">{title}</h2>
              {description ? (
                <p className="mt-0.5 text-[12.5px] text-muted">{description}</p>
              ) : null}
            </div>
          </div>
          {actions}
        </header>
      ) : null}
      <div className={flush ? undefined : 'p-5'}>{children}</div>
    </section>
  );
}

export type StatTone = 'accent' | 'ok' | 'warn' | 'bad' | 'info';

const STAT_TONES: Record<StatTone, string> = {
  accent: 'bg-accent-soft text-accent',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  bad: 'bg-bad-soft text-bad',
  info: 'bg-info-soft text-info',
};

export interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  /** Highlight the value as a problem (e.g. overdue > 0). */
  alert?: boolean;
  icon?: LucideIcon;
  tone?: StatTone;
}

export function StatCard({
  label,
  value,
  hint,
  alert,
  icon: Icon,
  tone = 'accent',
}: StatCardProps) {
  return (
    <div className="card flex items-center gap-4 px-5 py-4">
      {Icon ? (
        <span
          className={cn('grid size-12 shrink-0 place-items-center rounded-xl', STAT_TONES[tone])}
        >
          <Icon aria-hidden className="size-6" />
        </span>
      ) : null}
      <div className="min-w-0">
        <div className="text-[13px] font-medium text-muted">{label}</div>
        <div
          className={cn(
            'mt-0.5 text-[26px] leading-tight font-bold tabular-nums',
            alert && 'text-bad',
          )}
        >
          {value}
        </div>
        {hint ? <div className="text-xs text-faint">{hint}</div> : null}
      </div>
    </div>
  );
}
