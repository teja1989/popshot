# Popshot web image: the Next.js standalone server. Base images are pinned by digest.

FROM node:25-trixie-slim@sha256:aabbe39553d15ede8a97cc60c9e1a97034ff772afcf696ea42b94e7f5f2ec71b AS build
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /src
COPY package.json package-lock.json .npmrc ./
# Install scripts stay blocked; package.json lists the ones we deny.
RUN npm ci --no-audit --no-fund
COPY next.config.ts tsconfig.json ./
COPY src ./src
RUN npm run build

FROM node:25-trixie-slim@sha256:aabbe39553d15ede8a97cc60c9e1a97034ff772afcf696ea42b94e7f5f2ec71b AS runtime
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=8080
WORKDIR /app
# The standalone output carries only the runtime files Next.js traced as needed.
COPY --from=build --chown=10001:10001 /src/.next/standalone ./
COPY --from=build --chown=10001:10001 /src/.next/static ./.next/static
# npm isn't needed at runtime; removing it shrinks the attack surface.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx \
           /usr/local/lib/node_modules/corepack /usr/local/bin/corepack
USER 10001:10001
EXPOSE 8080
CMD ["node", "server.js"]
