/**
 * Display formatting. Conventions from the clickable demo (TODO(pilot-port):
 * confirm against the pilot's DateTime/money helpers):
 *  - dates en-GB, "16 Oct 2026", calendar dates read as UTC
 *  - date-times en-GB, "16 Oct, 14:05"
 *  - money en-US currency, USD by default
 *  - human codes zero-padded to 4 digits (CL-0001)
 */

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  // Calendar dates (YYYY-MM-DD) have no time zone: read them as UTC. Timestamps show
  // in the viewer's own zone (a meeting at 00:30 IST is on that day, not the day before).
  const dateOnly = iso.length === 10;
  const value = new Date(dateOnly ? `${iso}T00:00:00Z` : iso);
  return value.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    ...(dateOnly ? { timeZone: 'UTC' } : {}),
  });
}

export function formatDateTime(iso: string, timeZone?: string): string {
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  });
}

/** Amounts arrive from the API as decimal strings (NUMERIC(14,2)); numbers are accepted too. */
export function formatMoney(amount: string | number | null | undefined, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(
    Number(amount ?? 0),
  );
}

export function formatCode(prefix: string, value: number, width = 4): string {
  return `${prefix}-${String(value).padStart(width, '0')}`;
}

/** Indian-grouped rupees: 500000 → "₹5,00,000". */
export function formatINR(amount: string | number | null | undefined): string {
  if (amount === null || amount === undefined || amount === '') return '—';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: Number(amount) % 1 ? 2 : 0,
  }).format(Number(amount));
}

/** "2 hrs ago", "1 day ago", "just now" (mockup "Last activity"). */
export function timeAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return '—';
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  const units: [number, string][] = [
    [365 * 86400, 'year'],
    [30 * 86400, 'month'],
    [7 * 86400, 'week'],
    [86400, 'day'],
    [3600, 'hr'],
    [60, 'min'],
  ];
  for (const [size, unit] of units) {
    const value = Math.floor(seconds / size);
    if (value >= 1) return `${value} ${unit}${value === 1 ? '' : 's'} ago`;
  }
  return 'just now';
}

/** "10:30 AM" in the viewer's time zone. */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

/** Local calendar date of an ISO timestamp, as YYYY-MM-DD (for date inputs). */
export function localDateInput(date: Date = new Date()): string {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 10);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
