PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$PI_SCRIPTS/config.sh"

echo "=== [0/4] Preflight: checking nothing belonging to another project is at risk ==="

# --- cloudflared -------------------------------------------------------------
if [ -f "$CF_CONFIG_DIR/config.yml" ] && ! is_ours "$CF_CONFIG_DIR/config.yml"; then
  other_hosts=$(grep -oE 'hostname: .*' "$CF_CONFIG_DIR/config.yml" 2>/dev/null \
    | sed 's/hostname: //' | sort -u | tr '\n' ' ')
  echo "  ✓ $CF_CONFIG_DIR/config.yml belongs to another project (${other_hosts:-unknown host})."
  echo "    PickOne will NOT touch it. Its own config goes to $CF_CONFIG."
fi

if [ -f "$CF_CONFIG" ] && ! is_ours "$CF_CONFIG"; then
  die "$CF_CONFIG exists and was not written by this setup. Refusing to overwrite it."
fi

if [ -f "${SYSTEMD_DIR}/${CF_SERVICE}.service" ] \
   && ! is_ours "${SYSTEMD_DIR}/${CF_SERVICE}.service"; then
  die "${SYSTEMD_DIR}/${CF_SERVICE}.service exists and is not ours. Refusing to overwrite it."
fi

# --- host ports --------------------------------------------------------------
if ! command -v ss >/dev/null 2>&1; then
  echo "  ! 'ss' unavailable; skipping the port check."
else
  for port in "${HOST_PORTS[@]}"; do
    # No sudo: without root, ss still reports that the port is bound, and the
    # owner is identified through docker rather than through the process table.
    holder=$(ss -lntH "sport = :$port" 2>/dev/null | head -1)
    if [ -z "$holder" ]; then
      echo "  ✓ port $port is free."
      continue
    fi
    owner=$(docker ps --filter "publish=$port" --format '{{.Names}}' 2>/dev/null | head -1)
    case "$owner" in
      ${PROJECT}-*) echo "  ✓ port $port already held by our own container ($owner)." ;;
      "")           die "port $port is in use by a non-docker process:
    $holder" ;;
      *)            die "port $port is held by '$owner', another project.
    Change the host port in docker-compose.prod.yml AND scripts/pi/config.sh." ;;
    esac
  done
fi

# --- actions runner ----------------------------------------------------------
if [ -d "$HOME/actions-runner" ] && [ "$RUNNER_DIR" != "$HOME/actions-runner" ]; then
  echo "  ✓ \$HOME/actions-runner belongs to another project. Ours goes to $RUNNER_DIR."
fi

if [ -f "$RUNNER_DIR/.runner" ]; then
  registered=$(runner_repo "$RUNNER_DIR")
  case "$registered" in
    *"$REPO_SLUG")
      echo "  ✓ runner in $RUNNER_DIR is already registered to $REPO_SLUG." ;;
    "")
      # Fail closed. Step 4 rewrites $RUNNER_DIR/.env with our DEPLOY_DIR, so
      # proceeding against a directory we cannot identify risks breaking another
      # project's deploys. Unverifiable is not the same as safe.
      die "runner in $RUNNER_DIR has a registration we cannot read.
    Refusing to touch it. Move or delete that directory if it is stale." ;;
    *)
      die "runner in $RUNNER_DIR is registered to $registered, not $REPO_SLUG." ;;
  esac
fi

# --- docker compose project --------------------------------------------------
existing=$(docker compose ls --format json 2>/dev/null \
  | python3 -c "import sys,json;print(next((p['ConfigFiles'] for p in json.load(sys.stdin) if p['Name']=='${PROJECT}'),''))" 2>/dev/null || echo "")
if [ -n "$existing" ] && [[ "$existing" != "$DEPLOY_DIR"* ]]; then
  die "a docker compose project named '${PROJECT}' is already running from $existing."
fi

echo "  ✓ preflight passed — nothing belonging to another project will be modified."
echo ""
