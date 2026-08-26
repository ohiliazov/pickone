#!/usr/bin/env bash
# Read-only. Shows every host-level artefact PickOne owns, and confirms it has
# not taken over anything belonging to another project. Safe to run any time.
set -uo pipefail

PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$PI_SCRIPTS/config.sh"

fail=0
ok()   { echo "  ok    $*"; }
warn() { echo "  WARN  $*"; fail=1; }

echo "=== cloudflared ==="
for f in /etc/cloudflared/*.yml; do
  [ -e "$f" ] || continue
  hosts=$(grep -oE 'hostname: .*' "$f" 2>/dev/null | sed 's/hostname: //' | sort -u | tr '\n' ' ')
  if is_ours "$f"; then ok "$f (ours) -> ${hosts:-none}"
  else                  ok "$f (other project, untouched) -> ${hosts:-none}"; fi
done
[ -f "$CF_CONFIG" ] || warn "$CF_CONFIG is missing — run setup-pi.sh"
if [ -f "$CF_CONFIG_DIR/config.yml" ] && is_ours "$CF_CONFIG_DIR/config.yml"; then
  warn "we appear to own $CF_CONFIG_DIR/config.yml — that shared path should belong to the first project on this Pi"
fi

echo "=== systemd units ==="
for u in cloudflared "$CF_SERVICE"; do
  state=$(systemctl is-active "$u" 2>/dev/null || echo absent)
  [ "$state" = absent ] && continue
  [ "$u" = "$CF_SERVICE" ] && ok "$u: $state (ours)" || ok "$u: $state (other project)"
done

echo "=== host ports ==="
for port in "${HOST_PORTS[@]}"; do
  owner=$(docker ps --filter "publish=$port" --format '{{.Names}}' 2>/dev/null | head -1)
  case "$owner" in
    ${PROJECT}-*) ok   "$port -> $owner" ;;
    "")           ok   "$port -> free" ;;
    *)            warn "$port -> $owner (NOT ours)" ;;
  esac
done
echo "  --- other projects' published ports, for reference ---"
docker ps --format '{{.Names}}\t{{.Ports}}' 2>/dev/null \
  | grep -v "^${PROJECT}-" | grep '127.0.0.1' | sed 's/^/        /'

echo "=== actions runners ==="
for d in "$HOME"/actions-runner*; do
  [ -d "$d" ] || continue
  repo=$(runner_repo "$d"); repo="${repo:-unregistered}"
  [ "$d" = "$RUNNER_DIR" ] && ok "$d -> $repo (ours)" || ok "$d -> $repo (other project)"
done

echo "=== docker compose projects ==="
docker compose ls --format json 2>/dev/null | python3 -c "
import sys, json
for p in json.load(sys.stdin):
    print(f\"  ok    {p['Name']:12s} {p['Status']:16s} {p['ConfigFiles']}\")
" 2>/dev/null || echo "  (docker compose ls unavailable)"

echo ""
[ "$fail" -eq 0 ] && echo "No conflicts." || echo "Review the WARN lines above."
exit "$fail"
