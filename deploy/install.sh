#!/usr/bin/env bash
# OryvexSMTP VPS installer. Run once on a fresh server, as root.
# Usage: sudo ./deploy/install.sh example.com admin@example.com
set -euo pipefail
cd "$(dirname "$0")/.."

DOMAIN="${1:-}"
ACME_EMAIL="${2:-}"

fail() { echo "Error: $*" >&2; exit 1; }

[ -n "$DOMAIN" ] && [ -n "$ACME_EMAIL" ] || fail "usage: sudo ./deploy/install.sh <your-domain> <admin-email>"
[[ "$DOMAIN" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$ ]] || fail "use a lowercase domain like example.com"
[[ "$ACME_EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || fail "invalid admin email"
[ "$(id -u)" -eq 0 ] || fail "run as root (sudo) so config files can be owned by the mail user"
for tool in docker openssl curl; do command -v "$tool" >/dev/null || fail "$tool is required"; done
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"
[ ! -e instance/postal.yml ] || fail "already installed (instance/postal.yml exists). Delete it only if you want a fresh install."

PUBLIC_IP="${PUBLIC_IP:-$(curl -4 -fsS --max-time 10 https://api.ipify.org 2>/dev/null || true)}"
[[ "$PUBLIC_IP" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fail "could not detect public IPv4. Re-run with PUBLIC_IP=1.2.3.4 sudo -E ./deploy/install.sh ..."

umask 077
mkdir -p instance
DB_PASSWORD="$(openssl rand -hex 24)"
RAILS_SECRET="$(openssl rand -hex 64)"

openssl genrsa -out instance/signing.key 2048 2>/dev/null
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
  -keyout instance/smtp.key -out instance/smtp.cert \
  -subj "/CN=mail.${DOMAIN}" -addext "subjectAltName=DNS:mail.${DOMAIN}" 2>/dev/null

cat > instance/postal.yml <<EOF
version: 2

postal:
  web_hostname: mail.${DOMAIN}
  web_protocol: https
  smtp_hostname: mail.${DOMAIN}

web_server:
  default_bind_address: "0.0.0.0"

main_db:
  host: mariadb
  username: root
  password: ${DB_PASSWORD}
  database: oryvex

message_db:
  host: mariadb
  username: root
  password: ${DB_PASSWORD}
  prefix: oryvex

smtp_server:
  default_port: 25
  default_bind_address: "0.0.0.0"
  tls_enabled: true
  tls_certificate_path: /config/smtp.cert
  tls_private_key_path: /config/smtp.key

dns:
  mx_records:
    - mail.${DOMAIN}
  spf_include: spf.${DOMAIN}
  return_path_domain: rp.${DOMAIN}
  route_domain: routes.${DOMAIN}
  track_domain: track.${DOMAIN}
  helo_hostname: mail.${DOMAIN}

logging:
  rails_log_enabled: false
  highlighting_enabled: false

rails:
  environment: production
  secret_key: ${RAILS_SECRET}
EOF

cat > .env <<EOF
DOMAIN=${DOMAIN}
ACME_EMAIL=${ACME_EMAIL}
MARIADB_ROOT_PASSWORD=${DB_PASSWORD}
EOF

# The application runs as uid 999 inside the container.
chown -R 999:999 instance
chmod 700 instance
chmod 600 instance/*
chmod 600 .env

cat <<EOF

Config created. Create these DNS records at your DNS provider BEFORE continuing.
Use "DNS only" (no proxy) for every record.

  Type  Name            Value
  A     mail.${DOMAIN}       ${PUBLIC_IP}
  A     rp.${DOMAIN}         ${PUBLIC_IP}
  A     track.${DOMAIN}      ${PUBLIC_IP}
  MX    rp.${DOMAIN}         mail.${DOMAIN} (priority 10)
  TXT   spf.${DOMAIN}        v=spf1 ip4:${PUBLIC_IP} ~all

Also set reverse DNS (PTR) for ${PUBLIC_IP} to mail.${DOMAIN} in your VPS provider panel.
Open firewall ports: 22, 25, 80, 443, 587.

EOF

if [ "${SKIP_START:-0}" = "1" ]; then
  echo "SKIP_START=1: not starting containers."
  exit 0
fi

read -r -p "DNS records are in place and propagated? Start OryvexSMTP now [y/N] " answer
[[ "$answer" =~ ^[Yy]$ ]] || { echo "Start later with: docker compose -f docker-compose.vps.yml up -d --build"; exit 0; }

docker compose -f docker-compose.vps.yml up -d --build

cat <<EOF

OryvexSMTP is starting. Create your admin account:

  docker compose -f docker-compose.vps.yml run --rm oryvex-web postal make-user

Then open https://mail.${DOMAIN}
EOF
