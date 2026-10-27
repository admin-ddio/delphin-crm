/**
 * Choose a client's services: monthly retainers (SEO, Social Media) and one-off
 * projects (Website, Web App, Mobile App), each with an optional fee (money roles).
 */
import { useId } from 'react';

import { useServiceTypes, type ServiceKind, type ServiceSelection } from '@/features/services/api';
import { cn } from '@/lib/utils';

/** service key → fee as typed ('' = none); a key present means chosen. */
export type ServiceChoice = Record<string, string>;

export function toSelections(choice: ServiceChoice): ServiceSelection[] {
  return Object.entries(choice).map(([service_key, fee]) => ({
    service_key,
    fee: fee.trim() ? fee.trim() : null,
  }));
}

const GROUPS: { kind: ServiceKind; title: string; hint: string; fee: string }[] = [
  {
    kind: 'retainer',
    title: 'Monthly retainers',
    hint: 'Recurring monthly work. One of each per client.',
    fee: 'Monthly fee (INR)',
  },
  {
    kind: 'project',
    title: 'Projects',
    hint: 'One-off builds with phases from discovery to launch.',
    fee: 'Project value (INR)',
  },
];

export function ServicePicker({
  value,
  onChange,
  showFees,
  error,
  exclude = [],
}: {
  value: ServiceChoice;
  onChange(next: ServiceChoice): void;
  showFees: boolean;
  error?: string;
  /** Retainer keys the client already has (can't be chosen again). */
  exclude?: readonly string[];
}) {
  const types = useServiceTypes();
  const id = useId();
  if (types.isPending) return <p className="text-muted">Loading services…</p>;
  return (
    <div className="flex flex-col gap-4" data-testid="service-picker">
      {GROUPS.map((group) => (
        <fieldset key={group.kind} className="flex flex-col gap-2">
          <legend className="text-[13px] font-semibold">
            {group.title} <span className="font-normal text-muted">· {group.hint}</span>
          </legend>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {(types.data ?? [])
              .filter((t) => t.kind === group.kind && t.is_active)
              .map((t) => {
                const chosen = t.key in value;
                const blocked = exclude.includes(t.key);
                return (
                  <div
                    key={t.key}
                    className={cn(
                      'flex flex-col gap-2 rounded-lg border p-3',
                      chosen ? 'border-accent bg-accent-soft/40' : 'border-line',
                      blocked && 'opacity-60',
                    )}
                  >
                    <label className="flex items-center gap-2 text-[13.5px] font-medium">
                      <input
                        type="checkbox"
                        checked={chosen}
                        disabled={blocked}
                        onChange={(e) => {
                          const next = { ...value };
                          if (e.target.checked) next[t.key] = '';
                          else delete next[t.key];
                          onChange(next);
                        }}
                      />
                      {t.name}
                      {blocked ? (
                        <span className="text-xs text-muted">(already active)</span>
                      ) : null}
                    </label>
                    {chosen && showFees ? (
                      <div className="label">
                        <label htmlFor={`${id}-${t.key}`} className="text-xs">
                          {group.fee}
                        </label>
                        <input
                          id={`${id}-${t.key}`}
                          className="input"
                          inputMode="decimal"
                          placeholder="Optional"
                          value={value[t.key]}
                          onChange={(e) => onChange({ ...value, [t.key]: e.target.value })}
                        />
                      </div>
                    ) : null}
                  </div>
                );
              })}
          </div>
        </fieldset>
      ))}
      {error ? <p className="text-[12.5px] text-bad">{error}</p> : null}
    </div>
  );
}
