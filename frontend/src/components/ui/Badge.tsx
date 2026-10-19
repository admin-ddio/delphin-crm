/**
 * PROVISIONAL (look from the clickable demo's `.pill`). Replace with a verbatim
 * port of the pilot's Badge/StatusBadge (status → tone map, exact text).
 */
import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

export type BadgeTone = 'neutral' | 'accent' | 'ok' | 'warn' | 'bad' | 'info';

const tones: Record<BadgeTone, string> = {
  neutral: 'border-line bg-sunk text-muted',
  accent: 'border-accent/20 bg-accent-soft text-accent-strong',
  ok: 'border-ok/25 bg-ok-soft text-ok',
  warn: 'border-warn/25 bg-warn-soft text-warn',
  bad: 'border-bad/25 bg-bad-soft text-bad',
  info: 'border-info/20 bg-info-soft text-info',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

export function Badge({ tone = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
