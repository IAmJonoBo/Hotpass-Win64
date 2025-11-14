# Hotpass Web UI - Docker Image
# Multi-stage build for production-ready React app

FROM node:24-alpine AS builder

ARG PNPM_VERSION=9.12.2

ARG PREFECT_API_URL=http://localhost:4200/api
ARG OPENLINEAGE_URL=http://localhost:5000/api/v1
ARG E2E_GUIDE_URL=/docs/e2e-walkthrough.md

ENV PREFECT_API_URL=${PREFECT_API_URL}
ENV OPENLINEAGE_URL=${OPENLINEAGE_URL}
ENV VITE_PREFECT_API_URL=${PREFECT_API_URL}
ENV VITE_MARQUEZ_API_URL=${OPENLINEAGE_URL}
ENV VITE_E2E_GUIDE_URL=${E2E_GUIDE_URL}

WORKDIR /app

COPY apps/web-ui/package*.json ./
COPY apps/web-ui/pnpm-lock.yaml ./
RUN corepack enable pnpm \
 && corepack prepare pnpm@${PNPM_VERSION} --activate \
 && pnpm install --frozen-lockfile

COPY apps/web-ui ./
RUN mkdir -p public/docs
COPY docs/how-to-guides/e2e-walkthrough.md public/docs/e2e-walkthrough.md
COPY tools.json public/tools.json
RUN pnpm run build

FROM node:24-alpine AS runner

ARG PNPM_VERSION=9.12.2

ENV NODE_ENV=production
ENV PORT=3000

# Create and use a non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY apps/web-ui/package*.json ./
COPY apps/web-ui/pnpm-lock.yaml ./
RUN corepack enable pnpm \
 && corepack prepare pnpm@${PNPM_VERSION} --activate \
 && pnpm install --frozen-lockfile --prod

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server ./server

RUN mkdir -p ./dist/import ./dist/contracts \
  && chown -R appuser:appgroup ./dist ./server ./package*.json ./pnpm-lock.yaml

USER appuser

EXPOSE 3000

# Add a simple healthcheck (adjust path if needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server/index.mjs"]
