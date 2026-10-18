import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

/** Read-only pilot reference: PILOT_DIR in containers, the repo path otherwise. */
export const PILOT_DIR = process.env.PILOT_DIR ?? resolve(here, '../../reference/pilot');

export const PILOT_GLOBALS_CSS = resolve(PILOT_DIR, 'nextjs-app/src/app/globals.css');
export const PILOT_SCREENSHOTS = resolve(PILOT_DIR, 'screenshots');

export const pilotPresent = (): boolean => existsSync(PILOT_GLOBALS_CSS);

/** In CI, a missing pilot is a failure, not a skip (set REQUIRE_PILOT=true once it is committed). */
export const pilotRequired = (): boolean => process.env.REQUIRE_PILOT === 'true';
