/**
 * Firebase Auth in the browser (ADR-0009): verifies passwords, sends verification
 * and password-reset e-mails. The app session itself is our HttpOnly cookie, so
 * Firebase state is kept in memory only (nothing in localStorage/IndexedDB).
 *
 * Config comes from VITE_FIREBASE_* (public web-app values). In development
 * VITE_FIREBASE_USE_EMULATOR=true routes every call to the local Auth Emulator
 * through the Vite proxy on this same origin.
 */
import { initializeApp, type FirebaseApp } from 'firebase/app';
import {
  connectAuthEmulator,
  inMemoryPersistence,
  initializeAuth,
  type Auth,
} from 'firebase/auth';

let auth: Auth | null = null;

function createAuth(): Auth {
  const env = import.meta.env;
  const app: FirebaseApp = initializeApp({
    apiKey: env.VITE_FIREBASE_API_KEY,
    authDomain: env.VITE_FIREBASE_AUTH_DOMAIN || undefined,
    projectId: env.VITE_FIREBASE_PROJECT_ID,
    appId: env.VITE_FIREBASE_APP_ID || undefined,
  });
  const instance = initializeAuth(app, { persistence: inMemoryPersistence });
  if (env.VITE_FIREBASE_USE_EMULATOR === 'true') {
    connectAuthEmulator(instance, window.location.origin, { disableWarnings: true });
  }
  return instance;
}

export function firebaseAuth(): Auth {
  auth ??= createAuth();
  return auth;
}

/** Where Firebase e-mail links send people back to after they finish. */
export const signInUrl = () => `${window.location.origin}/login`;

/** Human message for a Firebase Auth error code. */
export function firebaseErrorMessage(error: unknown): string {
  const code = (error as { code?: string } | null)?.code ?? '';
  switch (code) {
    case 'auth/invalid-credential':
    case 'auth/invalid-login-credentials':
    case 'auth/wrong-password':
    case 'auth/user-not-found':
    case 'auth/invalid-email':
      return 'Invalid email or password.';
    case 'auth/too-many-requests':
      return 'Too many attempts. Wait a few minutes, or reset your password.';
    case 'auth/user-disabled':
      return 'This account has been disabled. Contact an administrator.';
    case 'auth/email-already-in-use':
      return 'An account with this e-mail already exists. Sign in instead.';
    case 'auth/weak-password':
      return 'Choose a stronger password.';
    case 'auth/expired-action-code':
    case 'auth/invalid-action-code':
      return 'This link is invalid or has expired. Ask for a new one.';
    case 'auth/requires-recent-login':
      return 'Please confirm your current password again.';
    case 'auth/network-request-failed':
      return "Couldn't reach the sign-in service. Check your connection and try again.";
    default:
      return 'Something went wrong. Please try again.';
  }
}
