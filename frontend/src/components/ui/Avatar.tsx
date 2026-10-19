/**
 * Initials avatar (mockups: coloured circles with company/person initials).
 * The colour is derived from the name, so it is stable across pages.
 */
import { cn } from '@/lib/utils';

const PALETTE = [
  'bg-[#5534e8] text-white',
  'bg-[#e6f6ec] text-[#1f6b3a]',
  'bg-[#e8f0fe] text-[#2a62d8]',
  'bg-[#fff1d6] text-[#9a5b00]',
  'bg-[#fde7f1] text-[#b0215e]',
  'bg-[#e6f7f8] text-[#16707a]',
  'bg-[#efebfe] text-[#4424cf]',
];

export function initials(name: string, max = 3): string {
  const words = name
    .replace(/[^\p{L}\p{N}\s&]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return '?';
  if (words.length === 1) return words[0]!.slice(0, Math.min(max, 3)).toUpperCase();
  return words
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join('');
}

function hash(text: string) {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) | 0;
  return Math.abs(h);
}

const SIZES = {
  xs: 'size-7 text-[11px]',
  sm: 'size-9 text-xs',
  md: 'size-12 text-sm',
  lg: 'size-16 text-xl',
} as const;

export function Avatar({
  name,
  size = 'sm',
  className,
}: {
  name: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-grid shrink-0 place-items-center rounded-full font-bold tracking-tight',
        SIZES[size],
        PALETTE[hash(name) % PALETTE.length],
        className,
      )}
    >
      {initials(name, size === 'lg' || size === 'md' ? 3 : 2)}
    </span>
  );
}
