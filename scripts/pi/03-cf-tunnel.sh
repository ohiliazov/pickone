PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$PI_SCRIPTS/config.sh"

echo "=== [3/4] Creating the Cloudflare Tunnel ==="
if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
  echo "You will be prompted to authenticate with Cloudflare."
  cloudflared tunnel login
else
  echo "Cloudflare already authenticated."
fi

if cloudflared tunnel info "$CF_TUNNEL_NAME" &>/dev/null; then
  echo "Tunnel '$CF_TUNNEL_NAME' already exists."
  TUNNEL_ID=$(cloudflared tunnel info "$CF_TUNNEL_NAME" | grep -oP '[0-9a-f-]{36}' | head -1)
else
  TUNNEL_ID=$(cloudflared tunnel create "$CF_TUNNEL_NAME" | grep -oP '[0-9a-f-]{36}' | head -1)
  echo "Created tunnel: $TUNNEL_ID"
fi

if [ -f /etc/cloudflared/config.yml ] \
   && DOMAIN=$(grep -m1 '^\s*- hostname:' /etc/cloudflared/config.yml | awk '{print $NF}') \
   && [ -n "$DOMAIN" ]; then
  echo "Domain already routed: $DOMAIN"
else
  read -rp "Domain to route (e.g. pickone.example.com): " DOMAIN
  cloudflared tunnel route dns "$CF_TUNNEL_NAME" "$DOMAIN"
fi

sudo mkdir -p /etc/cloudflared
sed -e "s/TUNNEL_ID/${TUNNEL_ID}/g" -e "s/yourdomain\.com/${DOMAIN}/g" -e '/^#/d' \
  "$DEPLOY_DIR/cloudflared/config.yml" | sudo tee /etc/cloudflared/config.yml > /dev/null

sudo mkdir -p /root/.cloudflared
sudo cp "$HOME/.cloudflared/${TUNNEL_ID}.json" "/root/.cloudflared/${TUNNEL_ID}.json"

if ! systemctl is-active --quiet cloudflared; then
  sudo cloudflared service install
  sudo systemctl enable cloudflared
  sudo systemctl start cloudflared
else
  echo "cloudflared already running; restarting to pick up the new config..."
  sudo systemctl restart cloudflared
fi
echo "cloudflared status: $(systemctl is-active cloudflared)"

echo ""
echo "!! Before going live: add a Cloudflare Access policy on https://${DOMAIN}/logs"
echo "   Dozzle has no authentication of its own, and container logs are not public data."
