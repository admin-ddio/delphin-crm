/**
 * Screen 4 – Client Questionnaire (product mockup): a 7-step wizard (Business Goals,
 * Target Markets, Competitors, Brand Voice, Past SEO Work, Additional Information,
 * Summary) with goal cards, Save Draft / Next, Preview Summary and Download
 * Responses. Shared by the staff tab and the client's public link. The server
 * re-checks completeness on submit; the checks here mirror it for guidance.
 */
import {
  BadgeCheck,
  Check,
  Download,
  Eye,
  Globe,
  Megaphone,
  MoreHorizontal,
  Plus,
  ShoppingCart,
  Target,
  TrendingUp,
  Trash2,
  UserRound,
  UsersRound,
  ArrowRight,
  ArrowLeft,
  type LucideIcon,
} from 'lucide-react';
import { useId, useState } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { TextField } from '@/components/ui/Field';
import { TextAreaField } from '@/components/ui/Fields';
import type { Answers, QuestionnaireForm } from '@/features/onboarding/api';
import { cn } from '@/lib/utils';

const GOAL_ICONS: Record<string, [LucideIcon, string]> = {
  organic_traffic: [TrendingUp, 'bg-accent-soft text-accent'],
  leads: [UsersRound, 'bg-sunk text-fg'],
  sales: [ShoppingCart, 'bg-ok-soft text-ok'],
  brand_awareness: [Megaphone, 'bg-accent-soft text-accent'],
  reputation: [BadgeCheck, 'bg-warn-soft text-warn'],
  keywords: [Target, 'bg-bad-soft text-bad'],
  new_markets: [Globe, 'bg-info-soft text-info'],
  engagement: [UserRound, 'bg-ok-soft text-ok'],
  other: [MoreHorizontal, 'bg-warn-soft text-warn'],
};

const YES_NO = [
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
  { value: 'unsure', label: 'Not sure' },
] as const;

type SectionKey =
  'business_goals' | 'target_markets' | 'competitors' | 'brand_voice' | 'past_seo' | 'additional';

const has = (value: string | null | undefined) => Boolean(value && value.trim());

/** Mirrors onboarding.questionnaire.missing_by_section on the server. */
export function missingFor(answers: Answers): Record<SectionKey, string[]> {
  const goals = answers.business_goals ?? {};
  const markets = answers.target_markets ?? {};
  const voice = answers.brand_voice ?? {};
  return {
    business_goals: [
      ...(goals.goals?.length ? [] : ['at least one goal']),
      ...(goals.goals?.includes('other') && !has(goals.other) ? ['the other goal'] : []),
      ...(has(goals.details) ? [] : ['your goals in detail']),
    ],
    target_markets: [
      ...(has(markets.locations) ? [] : ['target locations']),
      ...(has(markets.audiences) ? [] : ['target audiences']),
    ],
    competitors: (answers.competitors?.competitors ?? []).some((c) => has(c.name))
      ? []
      : ['at least one competitor'],
    brand_voice: voice.tones?.length ? [] : ['at least one tone'],
    past_seo: answers.past_seo?.worked_before ? [] : ['whether SEO was done before'],
    additional: [],
  };
}

function download(clientName: string, form: QuestionnaireForm, answers: Answers) {
  const goal = (key: string) => form.goals.find((g) => g.key === key)?.label ?? key;
  const tone = (key: string) => form.tones.find((t) => t.key === key)?.label ?? key;
  const line = (label: string, value: string | null | undefined) =>
    `${label}: ${value?.trim() || '—'}`;
  const text = [
    `Onboarding questionnaire — ${clientName}`,
    '',
    '1. Business Goals',
    line('Goals', (answers.business_goals?.goals ?? []).map(goal).join(', ')),
    line('Other goal', answers.business_goals?.other),
    line('Details', answers.business_goals?.details),
    '',
    '2. Target Markets',
    line('Locations', answers.target_markets?.locations),
    line('Audiences', answers.target_markets?.audiences),
    line('Languages', answers.target_markets?.languages),
    '',
    '3. Competitors',
    ...(answers.competitors?.competitors ?? []).map((c) =>
      `- ${c.name ?? ''} ${c.website ?? ''}`.trim(),
    ),
    line('Notes', answers.competitors?.notes),
    '',
    '4. Brand Voice',
    line('Tones', (answers.brand_voice?.tones ?? []).map(tone).join(', ')),
    line('Guidelines', answers.brand_voice?.guidelines),
    line('Avoid', answers.brand_voice?.avoid),
    '',
    '5. Past SEO Work',
    line('SEO done before', answers.past_seo?.worked_before),
    line('Details', answers.past_seo?.details),
    line('Penalties', answers.past_seo?.penalties),
    line('Tools', answers.past_seo?.tools),
    '',
    '6. Additional Information',
    line('Products & services', answers.additional?.products_services),
    line('Notes', answers.additional?.notes),
  ].join('\n');
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `${clientName.replace(/[^\w-]+/g, '-')}-questionnaire.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

export interface WizardProps {
  clientName: string;
  form: QuestionnaireForm;
  readOnly?: boolean;
  submitLabel?: string;
  onSaveDraft?(answers: Answers): Promise<void>;
  onSubmit?(answers: Answers): Promise<void>;
  /** Show "Download Responses" (staff). */
  allowDownload?: boolean;
}

export function QuestionnaireWizard({
  clientName,
  form,
  readOnly,
  submitLabel = 'Submit answers',
  onSaveDraft,
  onSubmit,
  allowDownload,
}: WizardProps) {
  const [answers, setAnswers] = useState<Answers>(form.answers);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const ids = useId();
  const missing = missingFor(answers);
  const sections = form.sections;
  const summaryIndex = sections.length;
  const current = sections[index];
  const allMissing = sections.flatMap((s) =>
    (missing[s.key as SectionKey] ?? []).map((m) => `${s.label}: ${m}`),
  );

  const set = <K extends keyof Answers>(section: K, patch: Partial<NonNullable<Answers[K]>>) =>
    setAnswers((prev) => ({ ...prev, [section]: { ...(prev[section] ?? {}), ...patch } }));

  const guard = async (action: () => Promise<void>) => {
    setBusy(true);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  };

  const goals = answers.business_goals?.goals ?? [];
  const tones = answers.brand_voice?.tones ?? [];
  const competitors = answers.competitors?.competitors?.length
    ? answers.competitors.competitors
    : [{ name: '', website: '' }];
  const field = (name: string) => `${ids}-${name}`;

  return (
    <div className="flex flex-col gap-4">
      {allowDownload ? (
        <div className="flex justify-end">
          <Button variant="primary" onClick={() => download(clientName, form, answers)}>
            <Download aria-hidden className="size-4" />
            Download Responses
          </Button>
        </div>
      ) : null}
      <Card
        className="grid overflow-hidden md:grid-cols-[260px_1fr]"
        data-testid="questionnaire-wizard"
      >
        <nav
          aria-label="Questionnaire steps"
          className="flex flex-col gap-1 border-b border-line-soft p-4 md:border-r md:border-b-0"
        >
          <ol className="flex flex-col">
            {[...sections, { key: 'summary', label: 'Summary' }].map((s, i) => {
              const done = i < summaryIndex && !(missing[s.key as SectionKey] ?? []).length;
              const active = i === index;
              return (
                <li key={s.key} className="relative">
                  {i < summaryIndex ? (
                    <span
                      aria-hidden
                      className="absolute top-9 bottom-[-4px] left-[25px] w-px bg-line"
                    />
                  ) : null}
                  <button
                    type="button"
                    aria-current={active ? 'step' : undefined}
                    onClick={() => setIndex(i)}
                    className={cn(
                      'relative flex w-full cursor-pointer items-center gap-3 rounded-lg px-2.5 py-2.5 text-left text-sm',
                      active ? 'bg-accent-soft font-semibold text-accent' : 'text-fg hover:bg-sunk',
                    )}
                  >
                    <span
                      className={cn(
                        'grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold',
                        active
                          ? 'bg-accent text-white'
                          : done
                            ? 'bg-ok text-white'
                            : 'bg-sunk text-muted',
                      )}
                    >
                      {done && !active ? <Check aria-hidden className="size-4" /> : i + 1}
                    </span>
                    {s.label}
                  </button>
                </li>
              );
            })}
          </ol>
          <Button className="mt-4" onClick={() => setIndex(summaryIndex)}>
            <Eye aria-hidden className="size-4" />
            Preview Summary
          </Button>
        </nav>

        <div className="flex min-w-0 flex-col gap-5 p-6">
          {current ? (
            <div>
              <h2 className="text-lg font-semibold">
                {index + 1}. {current.label}
              </h2>
              <p className="mt-1 text-muted">{current.question}</p>
            </div>
          ) : (
            <div>
              <h2 className="text-lg font-semibold">{summaryIndex + 1}. Summary</h2>
              <p className="mt-1 text-muted">Check the answers before submitting.</p>
            </div>
          )}

          <fieldset disabled={readOnly || busy} className="flex flex-col gap-5">
            {current?.key === 'business_goals' ? (
              <>
                <div
                  className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
                  role="group"
                  aria-label="Business goals"
                >
                  {form.goals.map((goal) => {
                    const [Icon, tone] = GOAL_ICONS[goal.key] ?? [Target, 'bg-sunk'];
                    const selected = goals.includes(goal.key as (typeof goals)[number]);
                    return (
                      <button
                        key={goal.key}
                        type="button"
                        role="checkbox"
                        aria-checked={selected}
                        onClick={() =>
                          set('business_goals', {
                            goals: selected
                              ? goals.filter((g) => g !== goal.key)
                              : [...goals, goal.key as (typeof goals)[number]],
                          })
                        }
                        className={cn(
                          'relative flex cursor-pointer flex-col items-center gap-3 rounded-xl border px-4 py-6 text-center text-sm font-medium transition-colors disabled:cursor-default',
                          selected
                            ? 'border-accent bg-accent-soft/50 ring-1 ring-accent'
                            : 'border-line hover:border-accent/50',
                        )}
                      >
                        <span
                          aria-hidden
                          className={cn(
                            'absolute top-3 right-3 grid size-5 place-items-center rounded-full border-2',
                            selected ? 'border-accent' : 'border-line',
                          )}
                        >
                          {selected ? <span className="size-2.5 rounded-full bg-accent" /> : null}
                        </span>
                        <span className={cn('grid size-12 place-items-center rounded-full', tone)}>
                          <Icon aria-hidden className="size-6" />
                        </span>
                        {goal.key === 'other' ? 'Other (Please specify)' : goal.label}
                      </button>
                    );
                  })}
                </div>
                {goals.includes('other') ? (
                  <TextField
                    label="Other goal"
                    maxLength={200}
                    value={answers.business_goals?.other ?? ''}
                    onChange={(e) => set('business_goals', { other: e.target.value })}
                  />
                ) : null}
                <TextAreaField
                  label="Please describe your goals in detail"
                  maxLength={2000}
                  value={answers.business_goals?.details ?? ''}
                  onChange={(e) => set('business_goals', { details: e.target.value })}
                />
              </>
            ) : null}

            {current?.key === 'target_markets' ? (
              <>
                <TextAreaField
                  id={field('locations')}
                  label="Target locations"
                  hint="Countries, regions or cities you sell to."
                  maxLength={1000}
                  value={answers.target_markets?.locations ?? ''}
                  onChange={(e) => set('target_markets', { locations: e.target.value })}
                />
                <TextAreaField
                  label="Target audiences"
                  hint="Who buys from you: roles, industries, demographics."
                  maxLength={2000}
                  value={answers.target_markets?.audiences ?? ''}
                  onChange={(e) => set('target_markets', { audiences: e.target.value })}
                />
                <TextField
                  label="Languages"
                  maxLength={200}
                  value={answers.target_markets?.languages ?? ''}
                  onChange={(e) => set('target_markets', { languages: e.target.value })}
                />
              </>
            ) : null}

            {current?.key === 'competitors' ? (
              <>
                <ul className="flex flex-col gap-3">
                  {competitors.map((c, i) => (
                    <li key={i} className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
                      <TextField
                        label={`Competitor ${i + 1}`}
                        maxLength={200}
                        value={c.name ?? ''}
                        onChange={(e) => {
                          const next = [...competitors];
                          next[i] = { ...c, name: e.target.value };
                          set('competitors', { competitors: next });
                        }}
                      />
                      <TextField
                        label={`Competitor ${i + 1} website`}
                        maxLength={300}
                        value={c.website ?? ''}
                        onChange={(e) => {
                          const next = [...competitors];
                          next[i] = { ...c, website: e.target.value };
                          set('competitors', { competitors: next });
                        }}
                      />
                      <Button
                        aria-label={`Remove competitor ${i + 1}`}
                        onClick={() =>
                          set('competitors', { competitors: competitors.filter((_, j) => j !== i) })
                        }
                      >
                        <Trash2 aria-hidden className="size-4" />
                      </Button>
                    </li>
                  ))}
                </ul>
                {competitors.length < 10 ? (
                  <div>
                    <Button
                      onClick={() =>
                        set('competitors', {
                          competitors: [...competitors, { name: '', website: '' }],
                        })
                      }
                    >
                      <Plus aria-hidden className="size-4" />
                      Add competitor
                    </Button>
                  </div>
                ) : null}
                <TextAreaField
                  label="Notes about competitors"
                  maxLength={2000}
                  value={answers.competitors?.notes ?? ''}
                  onChange={(e) => set('competitors', { notes: e.target.value })}
                />
              </>
            ) : null}

            {current?.key === 'brand_voice' ? (
              <>
                <div role="group" aria-label="Brand tone" className="flex flex-wrap gap-2">
                  {form.tones.map((t) => {
                    const on = tones.includes(t.key as (typeof tones)[number]);
                    return (
                      <button
                        key={t.key}
                        type="button"
                        role="checkbox"
                        aria-checked={on}
                        onClick={() =>
                          set('brand_voice', {
                            tones: on
                              ? tones.filter((x) => x !== t.key)
                              : [...tones, t.key as (typeof tones)[number]],
                          })
                        }
                        className={cn(
                          'cursor-pointer rounded-full border px-4 py-2 text-sm font-medium',
                          on
                            ? 'border-accent bg-accent text-white'
                            : 'border-line hover:border-accent/50',
                        )}
                      >
                        {t.label}
                      </button>
                    );
                  })}
                </div>
                <TextAreaField
                  label="Brand guidelines"
                  hint="Style, vocabulary, examples you like."
                  maxLength={2000}
                  value={answers.brand_voice?.guidelines ?? ''}
                  onChange={(e) => set('brand_voice', { guidelines: e.target.value })}
                />
                <TextAreaField
                  label="Words or topics to avoid"
                  maxLength={1000}
                  value={answers.brand_voice?.avoid ?? ''}
                  onChange={(e) => set('brand_voice', { avoid: e.target.value })}
                />
              </>
            ) : null}

            {current?.key === 'past_seo' ? (
              <>
                {(
                  [
                    ['worked_before', 'Has SEO been done on the website before?'],
                    ['penalties', 'Any Google penalties or manual actions?'],
                  ] as const
                ).map(([key, question]) => (
                  <fieldset key={key} className="flex flex-col gap-2">
                    <legend className="mb-1 text-[13px] font-medium">{question}</legend>
                    <div className="flex flex-wrap gap-4">
                      {YES_NO.map((option) => (
                        <label key={option.value} className="flex items-center gap-2 text-sm">
                          <input
                            type="radio"
                            name={`${ids}-${key}`}
                            checked={answers.past_seo?.[key] === option.value}
                            onChange={() => set('past_seo', { [key]: option.value })}
                          />
                          {option.label}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
                <TextAreaField
                  label="What was done, and with what results?"
                  maxLength={2000}
                  value={answers.past_seo?.details ?? ''}
                  onChange={(e) => set('past_seo', { details: e.target.value })}
                />
                <TextField
                  label="Tools in use (e.g. GA4, Search Console, Semrush)"
                  maxLength={500}
                  value={answers.past_seo?.tools ?? ''}
                  onChange={(e) => set('past_seo', { tools: e.target.value })}
                />
              </>
            ) : null}

            {current?.key === 'additional' ? (
              <>
                <TextAreaField
                  label="Products and services"
                  maxLength={2000}
                  value={answers.additional?.products_services ?? ''}
                  onChange={(e) => set('additional', { products_services: e.target.value })}
                />
                <TextAreaField
                  label="Anything else we should know?"
                  maxLength={2000}
                  value={answers.additional?.notes ?? ''}
                  onChange={(e) => set('additional', { notes: e.target.value })}
                />
              </>
            ) : null}
          </fieldset>

          {!current ? (
            <div className="flex flex-col gap-4" data-testid="questionnaire-summary">
              {allMissing.length ? (
                <Alert tone="warn" title="Still missing">
                  <ul className="list-disc pl-5">
                    {allMissing.map((m) => (
                      <li key={m}>{m}</li>
                    ))}
                  </ul>
                </Alert>
              ) : (
                <Alert tone="ok" title="All required answers are in." />
              )}
              <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[200px_1fr]">
                <dt className="text-muted">Goals</dt>
                <dd>
                  {goals.map((g) => form.goals.find((x) => x.key === g)?.label).join(', ') || '—'}
                  {answers.business_goals?.details ? (
                    <div className="text-muted">{answers.business_goals.details}</div>
                  ) : null}
                </dd>
                <dt className="text-muted">Target markets</dt>
                <dd>
                  {answers.target_markets?.locations || '—'}
                  {answers.target_markets?.audiences ? (
                    <div className="text-muted">{answers.target_markets.audiences}</div>
                  ) : null}
                </dd>
                <dt className="text-muted">Competitors</dt>
                <dd>
                  {(answers.competitors?.competitors ?? [])
                    .filter((c) => c.name)
                    .map((c) => c.name)
                    .join(', ') || '—'}
                </dd>
                <dt className="text-muted">Brand voice</dt>
                <dd>
                  {tones.map((t) => form.tones.find((x) => x.key === t)?.label).join(', ') || '—'}
                </dd>
                <dt className="text-muted">Past SEO work</dt>
                <dd>
                  {YES_NO.find((o) => o.value === answers.past_seo?.worked_before)?.label ?? '—'}
                  {answers.past_seo?.details ? (
                    <div className="text-muted">{answers.past_seo.details}</div>
                  ) : null}
                </dd>
                <dt className="text-muted">Products &amp; services</dt>
                <dd>{answers.additional?.products_services || '—'}</dd>
              </dl>
            </div>
          ) : null}

          <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line-soft pt-5">
            <div className="flex gap-2">
              {index > 0 ? (
                <Button onClick={() => setIndex(index - 1)}>
                  <ArrowLeft aria-hidden className="size-4" />
                  Back
                </Button>
              ) : null}
              {!readOnly && onSaveDraft ? (
                <Button disabled={busy} onClick={() => void guard(() => onSaveDraft(answers))}>
                  Save Draft
                </Button>
              ) : null}
            </div>
            {current ? (
              <Button variant="primary" onClick={() => setIndex(index + 1)}>
                Next
                <ArrowRight aria-hidden className="size-4" />
              </Button>
            ) : !readOnly && onSubmit ? (
              <Button
                variant="primary"
                disabled={busy || allMissing.length > 0}
                onClick={() => void guard(() => onSubmit(answers))}
              >
                {submitLabel}
              </Button>
            ) : null}
          </div>
        </div>
      </Card>
    </div>
  );
}
