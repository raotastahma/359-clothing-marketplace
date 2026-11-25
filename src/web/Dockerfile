# Builds the Customer Web Next.js app and keeps the runtime image limited to production dependencies.
FROM public.ecr.aws/docker/library/node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM public.ecr.aws/docker/library/node:20-alpine AS prod-deps
WORKDIR /app
COPY package.json package-lock.json* ./
# Optional packages are not needed by next start and can otherwise pull dev tools into runtime.
RUN npm ci --omit=dev --omit=optional

FROM public.ecr.aws/docker/library/node:20-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM public.ecr.aws/docker/library/node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
CMD ["npm", "run", "start"]
