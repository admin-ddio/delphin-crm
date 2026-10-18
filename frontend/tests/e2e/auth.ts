import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { APIRequestContext } from '@playwright/test';

const here = dirname(fileURLToPath(import.meta.url));

/** Saved signed-in browser state (cookies), written by global-setup.ts. Git-ignored. */
export const AUTH_FILE = resolve(here, '.auth/user.json');

/**
 * Dev/test accounts in the Firebase Auth Emulator + app (`make e2e` creates them):
 *   E2E_EMAIL        verified, super_admin: signs in for most tests
 *   FLOWS_EMAIL      starts UNVERIFIED: used by the verification and reset journeys
 */
export const E2E_EMAIL = process.env.E2E_EMAIL ?? 'e2e@example.com';
export const E2E_PASSWORD = process.env.E2E_PASSWORD ?? 'e2e-password-not-secret';
export const FLOWS_EMAIL = process.env.E2E_FLOWS_EMAIL ?? 'e2e-flows@example.com';

export const SIGNED_OUT = { cookies: [], origins: [] };

const PROJECT = process.env.FIREBASE_PROJECT_ID ?? 'demo-delphin';
const API_KEY = process.env.VITE_FIREBASE_API_KEY ?? 'demo-api-key';
/** The emulator is reached through the app's own origin (Vite proxy). */
const IDT = '/identitytoolkit.googleapis.com/v1';
/** Emulator-only admin bearer token (never valid against real Firebase). */
const OWNER = { Authorization: 'Bearer owner' };

/** Firebase sign-in over REST (what the browser SDK does); returns the ID token. */
export async function firebaseIdToken(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<string> {
  const response = await request.post(`${IDT}/accounts:signInWithPassword?key=${API_KEY}`, {
    data: { email, password, returnSecureToken: true },
  });
  if (!response.ok()) throw new Error(`Firebase sign-in failed: ${await response.text()}`);
  return ((await response.json()) as { idToken: string }).idToken;
}

interface OobCode {
  email: string;
  requestType: 'VERIFY_EMAIL' | 'PASSWORD_RESET' | string;
  oobCode: string;
}

/** Latest e-mail link code the emulator "sent" to `email` (its outbox). */
export async function latestOobCode(
  request: APIRequestContext,
  email: string,
  requestType: 'VERIFY_EMAIL' | 'PASSWORD_RESET',
): Promise<string> {
  const response = await request.get(`/emulator/v1/projects/${PROJECT}/oobCodes`);
  const { oobCodes } = (await response.json()) as { oobCodes: OobCode[] };
  const match = oobCodes.filter((c) => c.email === email && c.requestType === requestType).at(-1);
  if (!match) throw new Error(`No ${requestType} e-mail for ${email} in the emulator outbox`);
  return match.oobCode;
}

/** Emulator admin: reset a test account (password, verified flag). */
export async function resetEmulatorAccount(
  request: APIRequestContext,
  email: string,
  changes: { password?: string; emailVerified?: boolean },
): Promise<void> {
  const lookup = await request.post(`${IDT}/projects/${PROJECT}/accounts:lookup`, {
    headers: OWNER,
    data: { email: [email] },
  });
  const { users } = (await lookup.json()) as { users?: { localId: string }[] };
  const localId = users?.[0]?.localId;
  if (!localId) throw new Error(`${email} not found in the emulator (run make e2e setup)`);
  const update = await request.post(`${IDT}/projects/${PROJECT}/accounts:update`, {
    headers: OWNER,
    data: { localId, ...changes },
  });
  if (!update.ok()) throw new Error(`Emulator update failed: ${await update.text()}`);
}
