import { describe, expect, it } from 'vitest';

import { formatCode, formatDate, formatDateTime, formatMoney } from '@/lib/format';

describe('format', () => {
  it('formats calendar dates en-GB in UTC', () => {
    expect(formatDate('2026-10-16')).toBe('16 Oct 2026');
    expect(formatDate('2026-01-02T23:30:00Z')).toBe('02 Jan 2026');
    expect(formatDate(null)).toBe('—');
  });

  it('formats date-times en-GB', () => {
    expect(formatDateTime('2026-10-16T14:05:00Z', 'UTC')).toBe('16 Oct, 14:05');
  });

  it('formats money en-US from strings or numbers', () => {
    expect(formatMoney('2500')).toBe('$2,500.00');
    expect(formatMoney(1234.5)).toBe('$1,234.50');
    expect(formatMoney(null)).toBe('$0.00');
  });

  it('pads human codes', () => {
    expect(formatCode('CL', 1)).toBe('CL-0001');
    expect(formatCode('INV-2026', 12)).toBe('INV-2026-0012');
  });
});
