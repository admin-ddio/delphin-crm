// @vitest-environment node
/**
 * Pixel-parity gate: frontend/src/styles/globals.css must be byte-for-byte the
 * pilot's src/app/globals.css (§8.1). Skipped only while the pilot is absent
 * and REQUIRE_PILOT is not set.
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { PILOT_GLOBALS_CSS, pilotPresent, pilotRequired } from '../pilot';

const here = dirname(fileURLToPath(import.meta.url));
const OURS = resolve(here, '../../src/styles/globals.css');

describe('design tokens', () => {
  it.runIf(!pilotPresent() && pilotRequired())('pilot globals.css is present', () => {
    expect.fail(`Pilot not found at ${PILOT_GLOBALS_CSS}; REQUIRE_PILOT=true`);
  });

  it.skipIf(!pilotPresent())('globals.css is identical to the pilot', () => {
    const ours = readFileSync(OURS);
    const pilot = readFileSync(PILOT_GLOBALS_CSS);
    expect(ours.equals(pilot), 'globals.css drifted from the pilot: copy it verbatim').toBe(true);
  });

  it('provisional stand-in is still marked as such until the pilot is ported', () => {
    const ours = readFileSync(OURS, 'utf8');
    if (!pilotPresent()) {
      expect(ours).toContain('PROVISIONAL');
    }
    expect(ours).toContain('@import "tailwindcss"');
  });
});
