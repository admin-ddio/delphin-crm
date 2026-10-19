/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const apiTarget = process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000';

// Dev only: the Firebase Auth Emulator is served on the app's own origin, so the
// browser (and the Playwright container) never needs to reach port 9099 directly.
const firebaseEmulator = process.env.FIREBASE_EMULATOR_PROXY_TARGET;
const firebaseProxy = firebaseEmulator
  ? Object.fromEntries(
      ['/identitytoolkit.googleapis.com', '/securetoken.googleapis.com', '/emulator'].map(
        (path) => [path, { target: firebaseEmulator, changeOrigin: true }],
      ),
    )
  : {};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // "frontend" is the Compose hostname the Playwright container uses.
    allowedHosts: ['localhost', 'frontend'],
    watch: { usePolling: process.env.VITE_USE_POLLING === 'true' },
    // Pre-compile the app at startup so the first visit to each page isn't slow
    // (noticeable on Windows bind mounts, and in the throw-away e2e stack).
    warmup: { clientFiles: ['./src/main.tsx', './src/features/**/*.tsx'] },
    // Same-origin in dev too: the browser only ever talks to :5173.
    proxy: { '/api': { target: apiTarget, changeOrigin: false }, ...firebaseProxy },
  },
  build: {
    sourcemap: true,
    target: 'es2022',
  },
  test: {
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    setupFiles: ['tests/unit/setup.ts'],
    css: false,
    restoreMocks: true,
    // The first lazy route chunk (Firebase SDK, zod, react-hook-form) is slow to load cold.
    testTimeout: 15_000,
  },
});
