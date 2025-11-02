# Hotpass Web UI - Docker Image
# Multi-stage build for production-ready React app

FROM node:24-alpine AS builder

ARG PREFECT_API_URL=http://localhost:4200/api
ARG OPENLINEAGE_URL=http://localhost:5000/api/v1

ENV PREFECT_API_URL=${PREFECT_API_URL}
ENV OPENLINEAGE_URL=${OPENLINEAGE_URL}
ENV VITE_PREFECT_API_URL=${PREFECT_API_URL}
ENV VITE_MARQUEZ_API_URL=${OPENLINEAGE_URL}
ENV SKIP_TOOLS_SYNC=1

WORKDIR /app

COPY apps/web-ui/package*.json ./
RUN npm ci

COPY tools.json ./public/tools.json
COPY apps/web-ui/ .
RUN npm run build

FROM node:24-alpine AS runner

ENV NODE_ENV=production
ENV PORT=3000

WORKDIR /app

COPY apps/web-ui/package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server ./server

EXPOSE 3000

CMD ["node", "server/index.mjs"]
