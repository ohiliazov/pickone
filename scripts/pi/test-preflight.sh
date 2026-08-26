#!/usr/bin/env bash
# Exercises the coexistence guards against simulated Pi states, in a sandbox.
#
# Runs anywhere — no Pi, no Docker, no root. The point is that "setup-pi.sh will
# not clobber trilens" is a tested claim rather than a careful-looking script.
#
#   bash scripts/pi/test-preflight.sh
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pass=0; fail=0
run_case() {
  local name="$1" expect="$2"; shift 2
  local sandbox; sandbox=$(mktemp -d)
  export CF_CONFIG_DIR="$sandbox/cloudflared" SYSTEMD_DIR="$sandbox/systemd" HOME="$sandbox/home"
  mkdir -p "$CF_CONFIG_DIR" "$SYSTEMD_DIR" "$HOME"
  "$@"
  out=$(bash -c ". '$SCRIPTS/config.sh'; . '$SCRIPTS/00-preflight.sh'" 2>&1); rc=$?
  local got="pass"; [ $rc -ne 0 ] && got="abort"
  if [ "$got" = "$expect" ]; then
    printf "  \033[32mPASS\033[0m  %-46s (%s)\n" "$name" "$got"; pass=$((pass+1))
  else
    printf "  \033[31mFAIL\033[0m  %-46s expected %s, got %s\n" "$name" "$expect" "$got"
    echo "$out" | sed 's/^/          /' | tail -4; fail=$((fail+1))
  fi
  rm -rf "$sandbox"
}

trilens_present() {
  cat > "$CF_CONFIG_DIR/config.yml" <<'YML'
tunnel: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
ingress:
  - hostname: trilens.ohiliazov.com
    service: http://localhost:3000
  - service: http_status:404
YML
  mkdir -p "$HOME/actions-runner"
  echo '{"gitHubUrl": "https://github.com/ohiliazov/trilens"}' > "$HOME/actions-runner/.runner"
}
foreign_pickone_yml() { trilens_present; echo "# someone else's file" > "$CF_CONFIG_DIR/pickone.yml"; }
our_pickone_yml()     { trilens_present; echo "# managed by pickone — scripts/setup-pi.sh. Do not edit by hand." > "$CF_CONFIG_DIR/pickone.yml"; }
foreign_unit()        { trilens_present; echo "# hand-written" > "$SYSTEMD_DIR/cloudflared-pickone.service"; }
wrong_repo_runner()   { trilens_present; mkdir -p "$HOME/actions-runner-pickone"
                        echo '{"gitHubUrl": "https://github.com/ohiliazov/trilens"}' > "$HOME/actions-runner-pickone/.runner"; }
right_repo_runner()   { trilens_present; mkdir -p "$HOME/actions-runner-pickone"
                        echo '{"gitHubUrl": "https://github.com/ohiliazov/pickone"}' > "$HOME/actions-runner-pickone/.runner"; }

echo "=== preflight guards ==="
run_case "clean Pi"                              pass  true
run_case "trilens already installed"             pass  trilens_present
run_case "our own config from a previous run"    pass  our_pickone_yml
run_case "runner already ours"                   pass  right_repo_runner
run_case "foreign file at our config path"       abort foreign_pickone_yml
run_case "foreign systemd unit at our unit name" abort foreign_unit
run_case "our runner dir registered to trilens"  abort wrong_repo_runner

echo ""
echo "=== hostname collision guard ==="
sandbox=$(mktemp -d); export CF_CONFIG_DIR="$sandbox/cloudflared"; mkdir -p "$CF_CONFIG_DIR"
cat > "$CF_CONFIG_DIR/config.yml" <<'YML'
ingress:
  - hostname: trilens.ohiliazov.com
    service: http://localhost:3000
YML
check_host() {
  local host="$1" expect="$2"
  if bash -c ". '$SCRIPTS/config.sh'; hostname_owned_elsewhere '$host' >/dev/null" 2>/dev/null; then
    got="taken"; else got="free"; fi
  if [ "$got" = "$expect" ]; then
    printf "  \033[32mPASS\033[0m  %-46s (%s)\n" "$host" "$got"; pass=$((pass+1))
  else
    printf "  \033[31mFAIL\033[0m  %-46s expected %s, got %s\n" "$host" "$expect" "$got"; fail=$((fail+1))
  fi
}
check_host "trilens.ohiliazov.com" taken
check_host "pickone.ohiliazov.com" free
rm -rf "$sandbox"

echo ""
echo "  $pass passed, $fail failed"
exit $fail
