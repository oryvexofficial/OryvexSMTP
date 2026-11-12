# OryvexSMTP GitHub Actions & Web Portal

See [HOWTO.md](../HOWTO.md) for full instructions on running the workflow and accessing the web portal.

The workflow:
- Spawns OryvexSMTP / Postal in CI mode.
- Launches the lightweight Web Portal in `web/`.
- Opens a public `*.trycloudflare.com` tunnel.
- Provides an interactive web UI with an entry form to send test emails to `faketype3@gmail.com` with real-time protocol logs.
