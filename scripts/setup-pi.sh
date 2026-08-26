#!/usr/bin/env bash
# Run once on the Raspberry Pi, after cloning the repo.
# Usage: bash scripts/setup-pi.sh
#
# Idempotent: every step checks before it acts, so re-running is safe.
set -euo pipefail

PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")/pi" && pwd)"

. "$PI_SCRIPTS/config.sh"
. "$PI_SCRIPTS/01-docker.sh"
. "$PI_SCRIPTS/02-cloudflared.sh"
. "$PI_SCRIPTS/03-cf-tunnel.sh"
. "$PI_SCRIPTS/04-gha-runner.sh"

set +euo pipefail

cat <<NEXT

=== Setup complete ===

PickOne needs no Elasticsearch and no Redis, so there is no vm.max_map_count
step and nothing to tune for the JVM. Postgres is the only datastore.

Next steps:
  1. Create the production environment file:
       cp $DEPLOY_DIR/.env.prod.example $DEPLOY_DIR/.env.prod
       nano $DEPLOY_DIR/.env.prod
     Generate the secret with:
       python3 -c "import secrets; print(secrets.token_hex(32))"

  2. Start the stack (migrations run automatically as the 'migrate' service):
       cd $DEPLOY_DIR
       docker compose -f docker-compose.prod.yml up -d

  3. Check it:
       curl -s localhost:8100/readyz
       curl -s -o /dev/null -w '%{http_code}\n' localhost:3100/

  4. Add a Cloudflare Access policy on /logs before going live.

  5. From your dev machine: bump VERSION, commit, push to main, then
       make push
     The pi-prod runner picks up the tag and deploys automatically.
NEXT
