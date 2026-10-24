/** Reporting relationships as a labelled list: kind, line style, manager, source. */
import { Badge } from '@/components/ui/Badge';
import { Link } from '@/components/ui/Link';
import {
  LINE_STYLE,
  REPORTING_KINDS,
  SOURCE_LABELS,
  type Relation,
  type ReportingKind,
} from '@/features/team/api';
import { cn } from '@/lib/utils';

/** A short sample of the line style next to its text label (never colour alone). */
export function LineSample({ kind }: { kind: ReportingKind }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-block w-6 border-t-2 border-fg/70 align-middle',
        LINE_STYLE[kind].border,
      )}
    />
  );
}

export function LineLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Line styles">
      {(
        ['direct_manager', 'functional_manager', 'project_manager', 'department_head'] as const
      ).map((kind) => (
        <li key={kind} className="flex items-center gap-1.5">
          <LineSample kind={kind} />
          {REPORTING_KINDS.find((k) => k.value === kind)?.label}
        </li>
      ))}
    </ul>
  );
}

export function RelationList({
  relations,
  empty = 'No reporting relationships.',
  compact = false,
}: {
  relations: readonly Relation[];
  empty?: string;
  compact?: boolean;
}) {
  if (!relations.length) return <p className="text-muted">{empty}</p>;
  return (
    <ul className={cn('flex flex-col', compact ? 'gap-0.5 text-[12.5px]' : 'gap-1.5')}>
      {relations.map((r, index) => (
        <li
          key={`${r.kind}-${r.manager.id}-${r.project?.id ?? ''}-${index}`}
          className="flex flex-wrap items-center gap-1.5"
        >
          <LineSample kind={r.kind} />
          <span className="font-medium">{r.kind_label}:</span>
          <Link className="link" to={`/team/employees/${r.manager.id}`}>
            {r.manager.full_name}
          </Link>
          {r.project ? (
            <Badge tone="info">
              {r.project.code ? `${r.project.code} · ` : ''}
              {r.project.name}
            </Badge>
          ) : null}
          {r.source !== 'explicit' ? (
            <span className="text-xs text-muted">({SOURCE_LABELS[r.source]})</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
