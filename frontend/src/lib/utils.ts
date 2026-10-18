import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge class names, letting later Tailwind utilities win (same helper as the pilot). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
