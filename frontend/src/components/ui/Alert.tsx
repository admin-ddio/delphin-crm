/** PROVISIONAL (look from the clickable demo's `.callout`). Replace with the pilot's Alert. */
import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

export type AlertTone = 'info' | 'ok' | 'warn' | 'bad';

const tones: Record<AlertTone, string> = {
  info: 'border-line bg-accent-soft',
  ok: 'border-transparent bg-ok-soft',
  warn: 'border-transparent bg-warn-soft',
  bad: 'border-transparent bg-bad-soft',
};

export interface AlertProps {
  tone?: AlertTone;
  title?: string;
  children?: ReactNode;
  className?: string;
}

export function Alert({ tone = 'info', title, children, className }: AlertProps) {
  return (
    <div
      role={tone === 'bad' ? 'alert' : 'status'}
      className={cn('rounded-lg border px-3.5 py-[11px] text-[13px] text-fg', tones[tone], className)}
    >
      {title ? <b className="block">{title}</b> : null}
      {children}
    </div>
  );
}
