/**
 * PROVISIONAL (look from the clickable demo's `.panel`). Replace with a verbatim
 * port of the pilot's Card/StatCard.
 */
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
  className?: string;
  children?: ReactNode;
}

/** Card with an optional header (title, description, actions) and a body. */
export function Panel({ title, description, actions, flush, className, children }: PanelProps) {
  return (
    <section className={cn('card', className)}>
      {title ? (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line-soft px-3.5 py-3">
          <div>
            <h2 className="text-sm font-semibold">{title}</h2>
            {description ? <p className="mt-0.5 text-xs text-muted">{description}</p> : null}
          </div>
          {actions}
        </header>
      ) : null}
      <div className={flush ? undefined : 'p-3.5'}>{children}</div>
    </section>
  );
}

export interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  /** Highlight the value as a problem (e.g. overdue > 0). */
  alert?: boolean;
}

export function StatCard({ label, value, hint, alert }: StatCardProps) {
  return (
    <div className="card px-3.5 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div
        className={cn(
          'mt-0.5 font-mono text-2xl leading-tight font-semibold tabular-nums',
          alert && 'text-bad',
        )}
      >
        {value}
      </div>
      {hint ? <div className="text-[11.5px] text-faint">{hint}</div> : null}
    </div>
  );
}
