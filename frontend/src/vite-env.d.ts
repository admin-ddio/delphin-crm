/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FIREBASE_API_KEY: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN?: string;
  readonly VITE_FIREBASE_PROJECT_ID: string;
  readonly VITE_FIREBASE_APP_ID?: string;
  /** "true" in development: use the local Auth Emulator via the Vite proxy. */
  readonly VITE_FIREBASE_USE_EMULATOR?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
