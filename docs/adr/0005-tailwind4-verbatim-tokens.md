# 0005. Tailwind CSS 4.1 and a verbatim token port for pixel parity

- Status: accepted
- Date: 2026-10-16

## Context and problem statement

The rebuild must match the pilot pixel for pixel. The pilot styles everything with Tailwind 4
(`@theme` tokens in `globals.css`) and uses `lucide-react` icons.

## Decision drivers

- Identical CSS output for identical class strings.
- Identical icon geometry.

## Decision outcome

- Tailwind pinned to **4.1.x** (`@tailwindcss/vite` instead of PostCSS; only the import mechanics differ).
- `lucide-react` pinned to **0.545.x**.
- `frontend/src/styles/globals.css` is a **byte-for-byte copy** of the pilot's, guarded by a token-drift
  test, `.gitattributes -text`, and exclusions in prettier, pre-commit and the editorconfig.
- Pilot JSX and class strings are ported verbatim; only framework specifics change
  (`next/link` → React Router `Link`).
- Visual tests compare against the pilot screenshots at 1440 × 900 with ≤ 1% differing pixels.

### Consequences

- These packages must not be upgraded independently of a deliberate visual re-baseline.
- While the pilot is absent, `globals.css` holds a clearly marked provisional stand-in.
