PI_SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$PI_SCRIPTS/config.sh"

echo "=== [3/4] Cloudflare Tunnel (dedicated, alongside any existing tunnel) ==="

# One cloudflared binary can run any number of tunnels, each as its own systemd
# unit reading its own config file. PickOne therefore never touches
# /etc/cloudflared/config.yml and never runs `cloudflared service install` —
# both are owned by whichever project set the Pi up first.

if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
  echo "You will be prompted to authenticate with Cloudflare."
  cloudflared tunnel login
else
  echo "  ✓ Cloudflare already authenticated (shared account cert, not modified)."
fi

if cloudflared tunnel info "$CF_TUNNEL_NAME" &>/dev/null; then
  echo "  ✓ Tunnel '$CF_TUNNEL_NAME' already exists."
  TUNNEL_ID=$(cloudflared tunnel info "$CF_TUNNEL_NAME" | grep -oE '[0-9a-f-]{36}' | head -1)
else
  TUNNEL_ID=$(cloudflared tunnel create "$CF_TUNNEL_NAME" | grep -oE '[0-9a-f-]{36}' | head -1)
  echo "  ✓ Created tunnel: $TUNNEL_ID"
fi
[ -n "$TUNNEL_ID" ] || die "could not determine the tunnel id for '$CF_TUNNEL_NAME'."

if is_ours "$CF_CONFIG" \
   && DOMAIN=$(grep -m1 '^\s*- hostname:' "$CF_CONFIG" | awk '{print $NF}') \
   && [ -n "$DOMAIN" ]; then
  echo "  ✓ Domain already routed: $DOMAIN"
else
  read -rp "Domain to route (e.g. pickone.example.com): " DOMAIN
  [ -n "$DOMAIN" ] || die "no domain given."

  if owner=$(hostname_owned_elsewhere "$DOMAIN"); then
    die "$DOMAIN is already routed by $owner, which belongs to another project.
    Routing it here would steal that project's traffic. Pick a different hostname."
  fi

  cloudflared tunnel route dns "$CF_TUNNEL_NAME" "$DOMAIN"
fi

sudo mkdir -p /etc/cloudflared

# Strip the template's comments, substitute, and stamp our marker on line 1 so a
# re-run — or another project's setup — can tell whose file this is.
{
  echo "$MANAGED_MARKER"
  sed -e "s/TUNNEL_ID/${TUNNEL_ID}/g" -e "s/yourdomain\.com/${DOMAIN}/g" -e '/^\s*#/d' -e '/^$/d' \
    "$DEPLOY_DIR/cloudflared/config.yml"
} | sudo tee "$CF_CONFIG" > /dev/null
echo "  ✓ Wrote $CF_CONFIG (left \$CF_CONFIG_DIR/config.yml untouched)."

sudo mkdir -p /root/.cloudflared
sudo cp "$HOME/.cloudflared/${TUNNEL_ID}.json" "/root/.cloudflared/${TUNNEL_ID}.json"

# A dedicated unit, rather than `cloudflared service install`, which would
# overwrite the shared cloudflared.service and repoint it at config.yml.
sudo tee "/etc/systemd/system/${CF_SERVICE}.service" > /dev/null <<UNIT
$MANAGED_MARKER
[Unit]
Description=cloudflared tunnel (${PROJECT})
After=network-online.target
Wants=network-online.target

[Service]
TimeoutStartSec=0
Type=notify
ExecStart=/usr/bin/cloudflared --no-autoupdate --config ${CF_CONFIG} tunnel run
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable "$CF_SERVICE"
sudo systemctl restart "$CF_SERVICE"
echo "  ✓ ${CF_SERVICE}: $(systemctl is-active "$CF_SERVICE")"

if systemctl list-unit-files 2>/dev/null | grep -q '^cloudflared\.service'; then
  echo "  ✓ Existing cloudflared.service still: $(systemctl is-active cloudflared 2>/dev/null || echo 'not running')"
fi

echo ""
