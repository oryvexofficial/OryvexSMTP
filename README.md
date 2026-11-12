<p align="center">
  <img src="assets/banner.png" alt="OryvexSMTP: your mail, your server, your rules" width="900">
</p>

# OryvexSMTP

**Self-hosted mail delivery server for your own VPS, built on [Postal](https://github.com/postalserver/postal).**

You run it on a server you control. It sends directly to recipients' mail servers on port 25, with your own SPF, DKIM and DMARC. No third-party relay is involved. Postal's upstream copyright and MIT license are kept in [MIT-LICENCE](MIT-LICENCE).

## What you need

- A VPS with a **static public IPv4** and **outbound port 25 open**. Many providers block port 25 on new accounts: confirm before you buy, or ask support to unblock it.
- Ability to set **reverse DNS (PTR)** for the IP to `mail.yourdomain.com`.
- A domain whose DNS you can edit, 2 GB RAM or more, Docker with Compose v2.
- Open firewall ports: 22, 25, 80, 443 and 587.

## Install

```bash
git clone https://github.com/oryvexofficial/OryvexSMTP.git
cd OryvexSMTP
sudo ./deploy/install.sh yourdomain.com you@yourdomain.com
```

The installer generates fresh random secrets, a signing key and a TLS certificate, writes them to `instance/` and `.env` (both git-ignored), then **prints the DNS records to create for your server**. Add them (DNS only, no proxy), wait for propagation, answer `y`, then create your admin user:

```bash
docker compose -f docker-compose.vps.yml run --rm oryvex-web postal make-user
```

Open `https://mail.yourdomain.com` and sign in.

## Send mail from your domain

1. In the dashboard create an organization, a mail server, and add your sending domain.
2. Open the domain's **DNS Setup** page. It shows the exact SPF, DKIM and return-path records for that domain. Copy the full values; never publish shortened ones.
3. Add a DMARC record such as `_dmarc` TXT `v=DMARC1; p=none; rua=mailto:you@yourdomain.com`.
4. Create an SMTP credential for the mail server. Your apps connect to `mail.yourdomain.com` on port **587** (STARTTLS) or 25 with that credential.

## Operate

| Task | Command |
| --- | --- |
| Update | `git pull && docker compose -f docker-compose.vps.yml up -d --build` |
| Logs | `docker compose -f docker-compose.vps.yml logs -f oryvex-worker oryvex-smtp` |
| Stop | `docker compose -f docker-compose.vps.yml down` |
| Backup DB | `docker compose -f docker-compose.vps.yml exec mariadb sh -c 'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --all-databases' > backup.sql` |

Back up `instance/` and `.env` too: they hold your signing key and secrets. Losing them means regenerating DKIM keys.

## Good to know

- The web dashboard gets a Let's Encrypt certificate automatically through Caddy.
- SMTP STARTTLS uses a self-signed certificate by default. Most servers accept it, but you can mount a Let's Encrypt certificate and update `instance/postal.yml` (`smtp_server.tls_certificate_path` and `tls_private_key_path`).
- Delivery depends on IP reputation. Warm up slowly, keep complaints low, and check your IP against blocklists before sending at volume.
- Remote servers decide what lands in the inbox. Valid SPF, DKIM, DMARC and PTR are required, not a guarantee.
- The test-suite workflow in `.github/workflows/ci.yml` and `docker-compose.yml` is upstream test tooling only and uses a checked-in test key. It is not used for the server and must never be used in production.

## Credits

Based on [Postal](https://github.com/postalserver/postal). Docs: [docs.postalserver.io](https://docs.postalserver.io/).
