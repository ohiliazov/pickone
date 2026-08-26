echo "=== [2/4] Installing cloudflared ==="
if ! command -v cloudflared &>/dev/null; then
  curl -L --output cloudflared.deb \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
  sudo dpkg -i cloudflared.deb
  rm cloudflared.deb
else
  echo "cloudflared already installed: $(cloudflared --version)"
fi
