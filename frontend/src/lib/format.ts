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
  const value = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  return value.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
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
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(amount ?? 0));
}

export function formatCode(prefix: string, value: number, width = 4): string {
  return `${prefix}-${String(value).padStart(width, '0')}`;
}
