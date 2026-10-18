# syntax=docker/dockerfile:1.7
# Targets: dev (Vite dev server, used by compose.yaml) and runtime (nginx edge, compose.prod.yaml).

FROM node:22-alpine AS base
ENV CI=true
RUN npm install -g pnpm@10.17.0 \
 && mkdir -p /app && chown node:node /app
WORKDIR /app
USER node

FROM base AS deps
COPY --chown=node:node package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM deps AS dev
COPY --chown=node:node . .
EXPOSE 5173
HEALTHCHECK --interval=10s --timeout=5s --retries=12 \
  CMD wget -qO- http://127.0.0.1:5173/ > /dev/null || exit 1
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]

FROM deps AS build
# Vite inlines VITE_* at build time; these are public web-app values, not secrets.
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_APP_ID
ARG VITE_FIREBASE_USE_EMULATOR=false
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID \
    VITE_FIREBASE_USE_EMULATOR=$VITE_FIREBASE_USE_EMULATOR
COPY --chown=node:node . .
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.28-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --retries=6 \
  CMD wget -qO- http://127.0.0.1:8080/healthz-edge > /dev/null || exit 1
