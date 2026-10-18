/** PROVISIONAL (look from the clickable demo's `.empty`). Replace with the pilot's EmptyState. */
import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: LucideIcon;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon: Icon, action, className }: EmptyStateProps) {
  return (
    <div className={cn('px-4 py-[26px] text-center text-muted', className)}>
      {Icon ? <Icon aria-hidden className="mx-auto mb-2 size-6 text-faint" /> : null}
      <b className="mb-1 block text-fg">{title}</b>
      {description ? <div>{description}</div> : null}
      {action ? <div className="mt-2.5">{action}</div> : null}
    </div>
  );
}
