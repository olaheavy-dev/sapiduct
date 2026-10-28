# syntax=docker/dockerfile:1
# Owned by house-template-nextjs. The web image: Next.js's standalone server (output: "standalone"
# in next.config.ts), following Next.js's self-hosting guide. Dependencies are installed from the
# lockfile and the app is built in build stages; only the standalone server, its static assets and
# public/ reach the final image, which runs as a non-root user. The base image is pinned by digest;
# Dependabot updates it. Keep its major in step with .node-version (a test checks).
FROM node:26.12.1-trixie-slim@sha256:36793bcbb160a6a16cede1e62b93f84e26b78a972a8a4c0b879c1c12f22761ec AS base

FROM base AS build
ENV NEXT_TELEMETRY_DISABLED=1 \
    PNPM_HOME=/pnpm
WORKDIR /app
# pnpm at the version package.json's packageManager names.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN npm install --global --no-fund --no-audit "$(node -p 'require("./package.json").packageManager')"
# Dependencies first, in their own layer: it is rebuilt only when the lockfile changes.
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store
COPY . .
# The commit /health/live reports. Base's publish-image.yml passes it; the route is prerendered,
# so `next build` is what reads it (a local build without it reports null).
ARG GIT_COMMIT=""
# public/ is optional in a Next.js app, but the final stage copies it.
RUN pnpm build && mkdir -p public

FROM base
# The server needs only node: npm and npx go, and with them what they could install.
RUN rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
# HOSTNAME: listen on every interface, not only the container's own name. API_BASE_URL and the
# other settings are read at request time, so one image runs in every environment.
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=10001:10001 /app/.next/standalone ./
COPY --from=build --chown=10001:10001 /app/.next/static ./.next/static
COPY --from=build --chown=10001:10001 /app/public ./public
USER 10001:10001
EXPOSE 3000
# One process per container: scale with replicas. On SIGTERM the server finishes requests in
# flight and pending after() callbacks before it exits; give it 10-30 s (Next.js's guide).
CMD ["node", "server.js"]
