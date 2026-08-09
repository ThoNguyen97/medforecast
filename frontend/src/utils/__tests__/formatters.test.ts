import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  formatNumber,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatRelativeTime,
  formatPercent,
  formatQuantity,
  truncateText,
} from '../formatters';

describe('formatNumber', () => {
  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0');
  });

  it('formats a large number with thousand separators (vi-VN locale)', () => {
    const result = formatNumber(1000000);
    // vi-VN uses dots for thousands
    expect(result).toMatch(/1[.,\u202F]000[.,\u202F]?000/);
  });

  it('formats decimals when specified', () => {
    const result = formatNumber(3.14159, 2);
    expect(result).toContain('3');
    expect(result).toContain('14');
  });

  it('rounds to zero decimals by default', () => {
    const result = formatNumber(3.7);
    expect(result).toBe('4');
  });
});

describe('formatCurrency', () => {
  it('includes VND label', () => {
    const result = formatCurrency(50000);
    expect(result).toMatch(/50[.,\u202F]?000/);
    expect(result).toMatch(/₫|VND|đ/i);
  });

  it('formats zero currency', () => {
    const result = formatCurrency(0);
    expect(result).toMatch(/0/);
  });
});

describe('formatDate', () => {
  it('formats a date string to dd/mm/yyyy', () => {
    // Use a fixed date that won't depend on timezone offset for the year/month/day
    const result = formatDate('2024-01-15');
    expect(result).toMatch(/15/);
    expect(result).toMatch(/01|1/);
    expect(result).toMatch(/2024/);
  });

  it('accepts custom options', () => {
    const result = formatDate('2024-06-01', { year: 'numeric' });
    expect(result).toMatch(/2024/);
  });
});

describe('formatDateTime', () => {
  it('includes both date and time parts', () => {
    const result = formatDateTime('2024-01-15T10:30:00');
    expect(result).toMatch(/2024/);
    // Time parts - colon separator is universal
    expect(result).toMatch(/:/);
  });
});

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-06-01T12:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns "Vừa xong" for very recent times', () => {
    const now = new Date('2024-06-01T12:00:00');
    const result = formatRelativeTime(now.toISOString());
    expect(result).toBe('Vừa xong');
  });

  it('returns minutes ago for recent times', () => {
    const past = new Date('2024-06-01T11:45:00'); // 15 min ago
    const result = formatRelativeTime(past.toISOString());
    expect(result).toBe('15 phút trước');
  });

  it('returns hours ago for times within 24 hours', () => {
    const past = new Date('2024-06-01T10:00:00'); // 2 hours ago
    const result = formatRelativeTime(past.toISOString());
    expect(result).toBe('2 giờ trước');
  });

  it('returns days ago for times within a week', () => {
    const past = new Date('2024-05-29T12:00:00'); // 3 days ago
    const result = formatRelativeTime(past.toISOString());
    expect(result).toBe('3 ngày trước');
  });

  it('returns formatted date for times more than a week ago', () => {
    const past = new Date('2024-05-01T12:00:00'); // > 7 days ago
    const result = formatRelativeTime(past.toISOString());
    expect(result).toMatch(/2024/);
  });
});

describe('formatPercent', () => {
  it('formats with default 1 decimal', () => {
    expect(formatPercent(42.567)).toBe('42.6%');
  });

  it('formats with custom decimals', () => {
    expect(formatPercent(42.567, 0)).toBe('43%');
  });

  it('formats zero', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('formats 100', () => {
    expect(formatPercent(100)).toBe('100.0%');
  });
});

describe('formatQuantity', () => {
  it('returns value with unit', () => {
    const result = formatQuantity(500, 'cái');
    expect(result).toMatch(/500/);
    expect(result).toContain('cái');
  });

  it('formats large numbers with separators', () => {
    const result = formatQuantity(10000, 'hộp');
    expect(result).toMatch(/10[.,\u202F]?000/);
    expect(result).toContain('hộp');
  });
});

describe('truncateText', () => {
  it('returns text unchanged if shorter than max', () => {
    expect(truncateText('short', 100)).toBe('short');
  });

  it('returns text unchanged if equal to max', () => {
    expect(truncateText('exact', 5)).toBe('exact');
  });

  it('truncates and appends ellipsis if too long', () => {
    expect(truncateText('hello world', 5)).toBe('hello...');
  });

  it('handles empty string', () => {
    expect(truncateText('', 10)).toBe('');
  });
});
