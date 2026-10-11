# Local-only Firebase Auth emulator for development. Never built in CI or deployed.
#
# firebase-tools is pinned; its dependencies are resolved at build time, limited to versions
# published before NPM_BEFORE so a newly published package can't slip in. Some of those
# dependencies carry known advisories (proxy, FTP and file-watching libraries the Auth
# emulator doesn't use). That's accepted for a tool that only listens on your own machine.
# See dev/README.md.

FROM node:24-trixie-slim@sha256:173f125896c3b47ddf056734c7ea789d04595a6a08769a8f78e0df642781fb66

ARG FIREBASE_TOOLS_VERSION=15.31.0
ARG NPM_BEFORE=2026-09-24T00:00:00Z

ENV NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false \
    FIREBASE_CLI_DISABLE_UPDATE_CHECK=true

RUN npm install --global --ignore-scripts --before="${NPM_BEFORE}" \
      "firebase-tools@${FIREBASE_TOOLS_VERSION}" \
    && npm cache clean --force

COPY firebase.json /etc/popshot/firebase.json
# Runs with a read-only root filesystem; compose mounts tmpfs on the two places the CLI writes
# (its debug log in the working directory, its settings under HOME).
WORKDIR /emulator
USER node
EXPOSE 9099
# demo-* projects are Firebase's offline-only projects: nothing here can reach real resources.
CMD ["firebase", "emulators:start", "--only", "auth", "--project", "demo-popshot", \
     "--config", "/etc/popshot/firebase.json"]
