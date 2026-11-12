# OryvexSMTP Web Portal

A lightweight web dashboard and email testing portal for OryvexSMTP.

## Features

- **Web Dashboard**: Clean, responsive web UI to inspect SMTP server health.
- **Interactive Email Testing**: Form to compose and send test emails directly to any email address (e.g. `faketype3@gmail.com`).
- **Live SMTP Diagnostics**: Real-time terminal transcript showing full SMTP negotiation (`EHLO`, `AUTH`, `MAIL FROM`, `RCPT TO`, `DATA`, and status responses).
- **Session History**: Keeps track of recent test deliveries and outcomes.
- **Zero Dependencies**: Uses Python's built-in standard library (`http.server`, `smtplib`).

## Quick Start

Run locally or on a server:

```bash
# Optional configuration via environment variables:
export SMTP_HOST="127.0.0.1"
export SMTP_PORT="2525"
export SMTP_USERNAME="ci/smtp"
export SMTP_PASSWORD="postal-ci-key"
export SMTP_FROM="test@postal-ci.local"
export DEFAULT_TO="faketype3@gmail.com"
export WEB_PORT="8080"

python3 web/app.py
```

Then open your browser to `http://localhost:8080`.

## Cloudflare Tunnel (TryCloudflare)

To expose this portal to the public internet without port forwarding:

```bash
cloudflared tunnel --url http://127.0.0.1:8080
```

Cloudflare will output a public quick-tunnel URL like `https://<random-id>.trycloudflare.com`.
