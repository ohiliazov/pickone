#!/usr/bin/env bash
# Run once on the Raspberry Pi, after cloning the repo.
# Usage: bash scripts/setup-pi.sh
#
# Idempotent, and designed to share a Pi with other projects. Every host-level
# artefact it creates is namespaced (see scripts/pi/config.sh):
#
#   /etc/cloudflared/pickone.yml          not config.yml
#   cloudflared-pickone.service           not cloudflared.service
#   ~/actions-runner-pickone/             not ~/actions-runner/
#   runner label: pickone-prod            not pi-prod
#   host ports 8100 / 3100                not 8000 / 3000
#
# Step 0 verifies all of that before anything is written, and aborts rather
# than overwrite a file it does not recognise as its own.
set -euo pipefail

PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")/pi" && pwd)"

. "$PI_SCRIPTS/config.sh"
. "$PI_SCRIPTS/00-preflight.sh"
. "$PI_SCRIPTS/01-docker.sh"
. "$PI_SCRIPTS/02-cloudflared.sh"
. "$PI_SCRIPTS/03-cf-tunnel.sh"
. "$PI_SCRIPTS/04-gha-runner.sh"

set +euo pipefail

cat <<NEXT

=== Setup complete ===

PickOne needs no Elasticsearch and no Redis, so there is no vm.max_map_count
step and nothing to tune for a JVM. Postgres is the only datastore.

Nothing belonging to another project on this Pi was modified.

Next steps:
  1. Create the production environment file:
       cp $DEPLOY_DIR/.env.prod.example $DEPLOY_DIR/.env.prod
       nano $DEPLOY_DIR/.env.prod
     Generate the secret with:
       python3 -c "import secrets; print(secrets.token_hex(32))"

  2. Start the stack (migrations run as the 'migrate' service):
       cd $DEPLOY_DIR
       docker compose -f docker-compose.prod.yml up -d

  3. Check it:
       curl -s localhost:8100/readyz
       curl -s -o /dev/null -w '%{http_code}\n' localhost:3100/
       systemctl is-active $CF_SERVICE

  4. From your dev machine: bump VERSION, commit, push to main, then
       make push
     The $RUNNER_LABEL runner picks up the tag and deploys automatically.

To verify coexistence at any time:
       bash scripts/pi/coexistence-check.sh
NEXT
