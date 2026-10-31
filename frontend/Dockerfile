# syntax=docker/dockerfile:1
FROM node:20-alpine AS deps
WORKDIR /app
# Ставим строго по lockfile (npm ci) — детерминированная сборка, совпадает с CI.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Гарантируем существование public/ (git не хранит пустые каталоги),
# иначе COPY на стадии runner упадёт. Кэш Next переживает повторные сборки.
RUN --mount=type=cache,target=/app/.next/cache \
    mkdir -p public && npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
