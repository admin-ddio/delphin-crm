import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

import { request, type FullConfig } from '@playwright/test';

import { AUTH_FILE, E2E_EMAIL, E2E_PASSWORD, firebaseIdToken } from './auth';

const HINT =
  'Create the test accounts first:\n' +
  '  docker compose run --rm backend python scripts/dev_create_user.py ' +
  `${E2E_EMAIL} "E2E Admin" super_admin '<E2E_PASSWORD>'`;

/** Sign in once (Firebase emulator → app session) and save the cookies for app-page tests. */
export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use.baseURL;
  const context = await request.newContext({ baseURL });
  let idToken: string;
  try {
    idToken = await firebaseIdToken(context, E2E_EMAIL, E2E_PASSWORD);
  } catch (error) {
    throw new Error(`${(error as Error).message}\n${HINT}`);
  }
  const response = await context.post('/api/v1/auth/session', { data: { id_token: idToken } });
  if (!response.ok()) {
    throw new Error(`App session for ${E2E_EMAIL} failed (${response.status()}).\n${HINT}`);
  }
  mkdirSync(dirname(AUTH_FILE), { recursive: true });
  await context.storageState({ path: AUTH_FILE });
  await context.dispose();
}
