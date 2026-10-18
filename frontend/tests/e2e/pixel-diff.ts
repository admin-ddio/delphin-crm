import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import type { Page, TestInfo } from '@playwright/test';
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';

import { PILOT_SCREENSHOTS } from '../pilot';

export const MAX_DIFF_RATIO = 0.01;

export interface Clip {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function baselinePath(file: string): string {
  return resolve(PILOT_SCREENSHOTS, file);
}

export function hasBaseline(file: string): boolean {
  return existsSync(baselinePath(file));
}

function crop(png: PNG, clip: Clip): PNG {
  const out = new PNG({ width: clip.width, height: clip.height });
  PNG.bitblt(png, out, clip.x, clip.y, clip.width, clip.height, 0, 0);
  return out;
}

/** Freeze the page for deterministic captures: fonts loaded, no animation, no caret. */
export async function stabilise(page: Page): Promise<void> {
  await page.addStyleTag({
    content:
      '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}',
  });
  await page.evaluate(() => document.fonts.ready);
}

/**
 * Compare the page (or a clipped region) with a pilot baseline. Size mismatches
 * count as full failure. Attaches actual, expected and diff images to the report.
 */
export async function diffAgainstBaseline(
  page: Page,
  testInfo: TestInfo,
  file: string,
  clip?: Clip,
): Promise<number> {
  const expectedFull = PNG.sync.read(readFileSync(baselinePath(file)));
  const expected = clip ? crop(expectedFull, clip) : expectedFull;
  const actual = PNG.sync.read(
    await page.screenshot({ fullPage: !clip, clip, animations: 'disabled' }),
  );

  await testInfo.attach(`actual-${file}`, { body: PNG.sync.write(actual), contentType: 'image/png' });
  await testInfo.attach(`expected-${file}`, { body: PNG.sync.write(expected), contentType: 'image/png' });

  if (actual.width !== expected.width || actual.height !== expected.height) {
    testInfo.annotations.push({
      type: 'size-mismatch',
      description: `actual ${actual.width}×${actual.height} vs pilot ${expected.width}×${expected.height}`,
    });
    return 1;
  }

  const diff = new PNG({ width: actual.width, height: actual.height });
  const changed = pixelmatch(actual.data, expected.data, diff.data, actual.width, actual.height, {
    threshold: 0.1,
  });
  await testInfo.attach(`diff-${file}`, { body: PNG.sync.write(diff), contentType: 'image/png' });
  const ratio = changed / (actual.width * actual.height);
  testInfo.annotations.push({ type: 'diff-ratio', description: ratio.toFixed(5) });
  return ratio;
}
