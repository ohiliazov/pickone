echo "=== [1/4] Installing Docker (shared, idempotent) ==="
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  echo "Docker installed. Log out and back in for the group change to take effect."
else
  echo "Docker already installed: $(docker --version)"
fi
