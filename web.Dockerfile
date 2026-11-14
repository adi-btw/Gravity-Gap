# Gravity Gap web app (Next.js). Build context: repo root, so the prebuild step
# (web/scripts/copy-artifacts.mjs) can copy ../artifacts and ../ledger into web/public/artifacts.
#   docker build -f web.Dockerfile --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t gravity-gap-web .
#   docker run -p 3000:3000 gravity-gap-web
# NEXT_PUBLIC_API_URL is inlined into the client bundle at build time: it is the URL the *browser* calls.

FROM node:22-alpine AS builder
WORKDIR /repo
ENV NEXT_TELEMETRY_DISABLED=1
COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci
COPY artifacts ./artifacts
COPY ledger ./ledger
COPY web ./web
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN cd web && npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=builder --chown=node:node /repo/web/package.json /repo/web/next.config.ts ./
COPY --from=builder --chown=node:node /repo/web/node_modules ./node_modules
COPY --from=builder --chown=node:node /repo/web/public ./public
COPY --from=builder --chown=node:node /repo/web/.next ./.next
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -q -O /dev/null "http://127.0.0.1:${PORT}/" || exit 1
CMD ["sh", "-c", "exec node_modules/.bin/next start -H 0.0.0.0 -p ${PORT:-3000}"]
