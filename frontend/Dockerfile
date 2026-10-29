# Edezee frontend. The public API URL is baked in at build time, so it must be
# passed as a build arg (Next inlines NEXT_PUBLIC_* during `next build`).
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: no dependency may run a lifecycle script at install time.
RUN npm ci --ignore-scripts

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production PORT=3000
COPY --from=build --chown=node:node /app ./
# The base image already provides an unprivileged `node` user (uid 1000).
USER node
EXPOSE 3000
CMD ["sh", "-c", "npm run start -- -p ${PORT}"]
