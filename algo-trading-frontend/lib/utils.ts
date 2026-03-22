import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merges Tailwind CSS class names, resolving conflicts via tailwind-merge.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Formats a number as a USD currency string.
 * e.g. 12345.6 -> "$12,345.60"
 */
export function formatCurrency(
  value: number,
  currency = 'USD',
  locale = 'en-US'
): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Formats a decimal fraction as a percentage string.
 * e.g. 0.1234 -> "12.34%"
 */
export function formatPct(
  value: number,
  decimals = 2,
  locale = 'en-US'
): string {
  return new Intl.NumberFormat(locale, {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

/**
 * Formats a number with a fixed number of decimal places.
 * e.g. 1.23456 -> "1.23"
 */
export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

/**
 * Formats an ISO date string to a human-readable short date.
 * e.g. "2024-03-15T10:30:00Z" -> "Mar 15, 2024"
 */
export function formatDate(isoString: string): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(isoString));
}

/**
 * Returns a positive/negative sign prefix for display.
 */
export function signOf(value: number): string {
  return value >= 0 ? '+' : '';
}

/**
 * Clamps a number between min and max.
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
