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

COPY package*.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile

COPY public/tools.json ./public/tools.json
COPY . .
RUN pnpm run build

FROM node:24-alpine AS runner

ENV NODE_ENV=production
ENV PORT=3000

WORKDIR /app

COPY package*.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile --prod

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server ./server

EXPOSE 3000

CMD ["node", "server/index.mjs"]
