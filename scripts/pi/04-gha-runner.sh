PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$PI_SCRIPTS/config.sh"

echo "=== [4/4] GitHub Actions self-hosted runner (dedicated) ==="

# A runner directory holds one repo's registration and one .env carrying
# DEPLOY_DIR. Sharing $HOME/actions-runner between projects overwrites both, so
# PickOne gets its own directory, its own runner name, and its own label.

if [ -x "$RUNNER_DIR/run.sh" ]; then
  echo "  ✓ Runner binaries already present in $RUNNER_DIR."
else
  echo "  Downloading the latest actions-runner-linux-arm64 release..."
  mkdir -p "$RUNNER_DIR"
  RUNNER_VERSION=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
    | grep -Po '"tag_name": "v\K[0-9.]+')
  curl -fsSL -o "$RUNNER_DIR/actions-runner.tar.gz" \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"
  tar xzf "$RUNNER_DIR/actions-runner.tar.gz" -C "$RUNNER_DIR"
  rm -f "$RUNNER_DIR/actions-runner.tar.gz"
fi

# GitHub's documented way to expose custom env vars to job steps on a
# self-hosted runner. Scoped to this runner directory, so it cannot clobber
# another project's DEPLOY_DIR.
echo "DEPLOY_DIR=${DEPLOY_DIR}" > "$RUNNER_DIR/.env"

if [ -f "$RUNNER_DIR/.runner" ]; then
  echo "  ✓ Runner already registered to ${REPO_SLUG}."
else
  echo "  Register this runner with GitHub:"
  echo "    1. Open https://github.com/${REPO_SLUG}/settings/actions/runners/new"
  echo "    2. Copy the registration token shown there."
  read -rp "  Registration token: " RUNNER_TOKEN
  [ -n "$RUNNER_TOKEN" ] || die "no registration token given."
  (cd "$RUNNER_DIR" && ./config.sh --url "https://github.com/${REPO_SLUG}" \
    --token "$RUNNER_TOKEN" --name "$RUNNER_NAME" --labels "$RUNNER_LABEL" --unattended)
fi

# Scope the "already running?" check to OUR unit. A bare `actions.runner.*`
# glob matches another project's runner and would skip installing ours.
RUNNER_UNIT="actions.runner.$(echo "$REPO_SLUG" | tr '/' '-').${RUNNER_NAME}.service"

if systemctl is-active --quiet "$RUNNER_UNIT" 2>/dev/null; then
  echo "  ✓ Runner service already running: $RUNNER_UNIT"
else
  (cd "$RUNNER_DIR" && sudo ./svc.sh install && sudo ./svc.sh start)
fi
echo "  ✓ Runner: $(systemctl is-active "$RUNNER_UNIT" 2>/dev/null || echo unknown) (label: $RUNNER_LABEL)"
