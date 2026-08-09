import { describe, it, expect } from 'vitest';
import { cn } from '../cn';

describe('cn (classnames utility)', () => {
  it('joins truthy strings', () => {
    expect(cn('foo', 'bar')).toBe('foo bar');
  });

  it('filters out falsy values', () => {
    expect(cn('foo', false, undefined, null, 'bar')).toBe('foo bar');
  });

  it('returns empty string when all values are falsy', () => {
    expect(cn(false, undefined, null)).toBe('');
  });

  it('handles a single class', () => {
    expect(cn('only')).toBe('only');
  });

  it('handles empty call', () => {
    expect(cn()).toBe('');
  });

  it('conditionally includes a class', () => {
    const isActive = true;
    expect(cn('base', isActive && 'active')).toBe('base active');
  });

  it('conditionally excludes a class', () => {
    const isActive = false;
    expect(cn('base', isActive && 'active')).toBe('base');
  });
});
