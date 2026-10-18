# 0001. Single monorepo for backend, frontend and infrastructure

- Status: accepted
- Date: 2026-10-16

## Context and problem statement

The rebuild has a FastAPI backend, a React SPA, a database, container definitions and a read-only pilot
reference. The frontend's types are generated from the backend's OpenAPI schema, and feature ports touch
both sides at once.

## Decision drivers

- One feature port should be one change, reviewed together.
- The generated API client must always match the backend in the same commit.
- One command (`make`) for humans and CI.

## Considered options

1. One monorepo with `backend/`, `frontend/`, `infra/` and `docs/`
2. Separate repositories per tier

## Decision outcome

Option 1. Plain directories with per-tier tooling (uv, pnpm), tied together by the Makefile and Compose.
No JS/Python monorepo framework.

### Consequences

- Good: atomic cross-tier changes, `make gen-api-check` catches client drift in CI.
- Bad: CI runs everything on each change. Acceptable at this size; path filters can come later.
