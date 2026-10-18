/**
 * PROVISIONAL (layout from the clickable demo's `.head`): optional breadcrumb,
 * h1, muted sub-line, actions on the right. Replace with the pilot's PageHeader.
 */
import type { ReactNode } from 'react';

import { Link } from '@/components/ui/Link';

export interface Crumb {
  label: string;
  to: string;
}

export interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  crumb?: Crumb;
}

export function PageHeader({ title, description, actions, crumb }: PageHeaderProps) {
  return (
    <div className="mb-[18px] flex flex-wrap items-start justify-between gap-3">
      <div>
        {crumb ? (
          <div className="mb-1 text-xs text-muted">
            <Link to={crumb.to} className="text-accent hover:underline">
              {crumb.label}
            </Link>
          </div>
        ) : null}
        <h1 className="text-[21px] leading-tight font-bold tracking-[-0.01em] text-balance">
          {title}
        </h1>
        {description ? <p className="mt-1 max-w-[70ch] text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
