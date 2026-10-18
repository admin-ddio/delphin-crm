import '@testing-library/jest-dom/vitest';

import { cleanup, configure } from '@testing-library/react';
import { afterEach } from 'vitest';

// jsdom installs its own AbortSignal, which Node's (undici) Request rejects. React Router's
// data router builds a Request for every navigation, so drop the foreign signal in tests only.
const NodeRequest = globalThis.Request;
globalThis.Request = class extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      const { signal: _signal, ...rest } = init;
      super(input, rest);
    } else {
      super(input, init);
    }
  }
} as typeof Request;

// Lazy route chunks (zod, react-hook-form) load slowly on first use under the test transform.
configure({ asyncUtilTimeout: 5000 });

afterEach(() => {
  cleanup();
});
