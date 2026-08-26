# syntax=docker/dockerfile:1

# ── Dev base: deps at / so a volume mount at /app cannot clobber node_modules ──
FROM node:24-slim AS base
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json /
RUN --mount=type=cache,target=/root/.npm cd / && npm ci
ENV PATH="/node_modules/.bin:${PATH}"

# ── Development ───────────────────────────────────────────────────────────────
FROM base AS development
WORKDIR /app
ENV NODE_ENV=development
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ── Builder ───────────────────────────────────────────────────────────────────
FROM node:24-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .

# Next inlines NEXT_PUBLIC_* at build time, so the public origin is baked into
# the image. That is also what decides whether robots.txt allows crawling
# ([SPEC §14.8]) — an image built without NEXT_PUBLIC_ENV=production ships a
# "Disallow: /" and will quietly de-index the site.
ARG NEXT_PUBLIC_ENV=production
ARG NEXT_PUBLIC_BASE_URL
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_ENV=${NEXT_PUBLIC_ENV} \
    NEXT_PUBLIC_BASE_URL=${NEXT_PUBLIC_BASE_URL} \
    NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

# ── Runner: standalone bundle, ~150MB instead of ~1.2GB ───────────────────────
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN addgroup -S pickone && adduser -S pickone -G pickone

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER pickone

EXPOSE 3000
CMD ["node", "server.js"]
