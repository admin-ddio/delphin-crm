/**
 * PROVISIONAL (look from the clickable demo's `.pill`). Replace with a verbatim
 * port of the pilot's Badge/StatusBadge (status → tone map, exact text).
 */
import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

export type BadgeTone = 'neutral' | 'accent' | 'ok' | 'warn' | 'bad' | 'info';

const tones: Record<BadgeTone, string> = {
  neutral: 'bg-sunk text-muted',
  accent: 'bg-accent-soft text-accent-strong',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  bad: 'bg-bad-soft text-bad',
  info: 'bg-info-soft text-info',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

export function Badge({ tone = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-px text-[11.5px] font-medium whitespace-nowrap',
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
