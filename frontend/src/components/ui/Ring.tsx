/** Circular progress (mockups: "60% Complete", access 80%, KPI "63% Overall"). */
import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

export function Ring({
  value,
  size = 120,
  stroke = 10,
  tone = 'accent',
  label,
  children,
}: {
  value: number;
  size?: number;
  stroke?: number;
  tone?: 'accent' | 'ok';
  label: string;
  children?: ReactNode;
}) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-sunk"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct / 100)}
          className={cn(
            'transition-[stroke-dashoffset] duration-500',
            tone === 'ok' ? 'stroke-ok' : 'stroke-accent',
          )}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        {children ?? <span className="text-xl font-bold">{pct}%</span>}
      </div>
    </div>
  );
}
