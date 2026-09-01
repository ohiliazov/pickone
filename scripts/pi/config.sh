# Shared configuration for the Pi setup steps.
#
# COEXISTENCE: this Pi may already run other projects (trilens, for one). Every
# host-level artefact below is namespaced by $PROJECT so that nothing PickOne
# writes can collide with, or overwrite, another project's setup. If you add a
# new host-level file, service, directory or port, namespace it here first.

PROJECT="pickone"

_PI_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="${DEPLOY_DIR:-$(cd "$_PI_SCRIPTS_DIR/../.." && pwd)}"
REPO_URL="${REPO_URL:-git@github.com:ohiliazov/${PROJECT}.git}"
REPO_SLUG="${REPO_SLUG:-ohiliazov/${PROJECT}}"

# --- Cloudflare Tunnel -------------------------------------------------------
# NOT /etc/cloudflared/config.yml. That path is the default single-tunnel
# config and is owned by whichever project ran `cloudflared service install`
# first. PickOne runs its own tunnel from its own file, under its own unit.
CF_TUNNEL_NAME="${CF_TUNNEL_NAME:-$PROJECT}"
# The two directories are overridable so the preflight guards can be exercised
# in a sandbox; on the Pi they are always the real paths.
CF_CONFIG_DIR="${CF_CONFIG_DIR:-/etc/cloudflared}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
CF_CONFIG="${CF_CONFIG_DIR}/${PROJECT}.yml"
CF_SERVICE="cloudflared-${PROJECT}"

# --- GitHub Actions runner ---------------------------------------------------
# NOT $HOME/actions-runner. That directory holds another project's registration
# and its .env (which carries DEPLOY_DIR); reusing it silently breaks that
# project's deploys.
RUNNER_DIR="${RUNNER_DIR:-$HOME/actions-runner-${PROJECT}}"
RUNNER_NAME="pi-${PROJECT}"
# NOT `pi-prod`. A shared label lets another repo's workflow land on this
# runner, and deploy the wrong project from the wrong directory.
RUNNER_LABEL="${PROJECT}-prod"

# --- Host ports --------------------------------------------------------------
# Must match docker-compose.prod.yml. Checked by 00-preflight.sh.
HOST_PORTS=(8100 3100)

# Marker written into every file this setup generates, so a re-run can tell its
# own output from a file that belongs to somebody else.
MANAGED_MARKER="# managed by ${PROJECT} — scripts/setup-pi.sh. Do not edit by hand."

is_ours() { [ -f "$1" ] && head -1 "$1" | grep -qF "managed by ${PROJECT}"; }

# Which repo a runner directory is registered to, or "" if it cannot be read.
# .runner is JSON, so parse it as JSON rather than with a regex — and note that
# every caller must treat "" as a reason to STOP, not as permission to proceed.
runner_repo() {
  [ -f "$1/.runner" ] || { echo ""; return; }
  python3 -c "
import json,sys
try:
    print(json.load(open(sys.argv[1])).get('gitHubUrl',''))
except Exception:
    print('')
" "$1/.runner" 2>/dev/null
}

# Is this hostname already served by a tunnel config that is not ours?
# A hostname belongs to exactly one tunnel, so routing one that another project
# already serves silently steals its traffic.
hostname_owned_elsewhere() {
  local domain="$1" f
  for f in "$CF_CONFIG_DIR"/*.yml; do
    [ -e "$f" ] || continue
    [ "$f" = "$CF_CONFIG" ] && continue
    if grep -qE "hostname: *${domain}\\s*$" "$f" 2>/dev/null; then echo "$f"; return 0; fi
  done
  return 1
}

die() { echo "" >&2; echo "ABORTING: $*" >&2; exit 1; }
