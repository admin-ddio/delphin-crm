/**
 * PROVISIONAL (layout from the product owner's mockups, 2026-10-19): optional
 * "← Back to …" link, optional leading visual (e.g. an avatar), large h1, muted
 * sub-line, actions on the right. Replace with the pilot's PageHeader.
 */
import { ArrowLeft } from 'lucide-react';
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
  /** Shown to the left of the title (client logo, avatar). */
  leading?: ReactNode;
}

export function PageHeader({ title, description, actions, crumb, leading }: PageHeaderProps) {
  return (
    <div className="mb-6">
      {crumb ? (
        <div className="mb-3 text-[13px] text-muted">
          <Link to={crumb.to} className="inline-flex items-center gap-1.5 hover:text-accent">
            <ArrowLeft aria-hidden className="size-3.5" />
            Back to {crumb.label}
          </Link>
        </div>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-4">
          {leading}
          <div className="min-w-0">
            <h1 className="text-[26px] leading-tight font-bold tracking-[-0.02em] text-balance">
              {title}
            </h1>
            {description ? (
              <div className="mt-1.5 max-w-[80ch] text-muted">{description}</div>
            ) : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}
