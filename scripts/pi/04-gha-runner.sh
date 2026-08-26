PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$PI_SCRIPTS/config.sh"

echo "=== [4/4] Installing the GitHub Actions self-hosted runner ==="

RUNNER_DIR="$HOME/actions-runner"

if [ -x "$RUNNER_DIR/run.sh" ]; then
  echo "Runner binaries already present in $RUNNER_DIR."
else
  echo "Downloading the latest actions-runner-linux-arm64 release..."
  mkdir -p "$RUNNER_DIR"
  RUNNER_VERSION=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest \
    | grep -Po '"tag_name": "v\K[0-9.]+')
  curl -fsSL -o "$RUNNER_DIR/actions-runner.tar.gz" \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"
  tar xzf "$RUNNER_DIR/actions-runner.tar.gz" -C "$RUNNER_DIR"
  rm -f "$RUNNER_DIR/actions-runner.tar.gz"
fi

# GitHub's documented way to expose custom env vars to job steps on a
# self-hosted runner. This is how deploy.yml gets $DEPLOY_DIR.
echo "DEPLOY_DIR=${DEPLOY_DIR}" > "$RUNNER_DIR/.env"

if [ -f "$RUNNER_DIR/.runner" ]; then
  echo "Runner already registered."
else
  echo "Register this runner with GitHub:"
  echo "  1. Open https://github.com/${REPO_SLUG}/settings/actions/runners/new"
  echo "  2. Copy the registration token shown there."
  read -rp "Registration token: " RUNNER_TOKEN
  (cd "$RUNNER_DIR" && ./config.sh --url "https://github.com/${REPO_SLUG}" \
    --token "$RUNNER_TOKEN" --name pi-prod --labels pi-prod --unattended)
fi

if systemctl is-active --quiet 'actions.runner.*'; then
  echo "Runner service already running."
else
  (cd "$RUNNER_DIR" && sudo ./svc.sh install && sudo ./svc.sh start)
fi
echo "Runner service: $(systemctl is-active 'actions.runner.*' 2>/dev/null || echo unknown)"
