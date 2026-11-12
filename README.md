<p align="center">
  <img src="assets/banner.png" alt="OryvexSMTP: open-source mail infrastructure, built on Postal" width="900">
</p>

# OryvexSMTP

**Open-source mail infrastructure, built on [Postal](https://github.com/postalserver/postal).**

OryvexSMTP brings an Oryvex-inspired blue identity to Postal's mail server, with a manual GitHub Actions workflow for testing SMTP locally. The application remains a derivative of Postal; upstream copyright and the MIT license are preserved in [MIT-LICENCE](MIT-LICENCE).

## What is included

- A blue OryvexSMTP interface, icon, favicon and banner.
- A manual-only GitHub Actions workflow that builds Postal, starts MariaDB, and runs an SMTP acceptance test.
- A disposable test owner, SMTP credential and sender domain for CI.
- A separate manual workflow for the upstream RSpec suite.

## Start the SMTP test

1. Push the project to your repository's default branch.
2. Optional: add a repository secret named `POSTAL_CI_CREDENTIAL_KEY` under **Settings → Secrets and variables → Actions**. Without it, the test uses `postal-ci-key`.
3. Open **Actions → OryvexSMTP Service → Run workflow**.
4. Open the run and check **Verify SMTP Server and Send Test Email**.

The workflow uses `127.0.0.1:2525`, username `ci/smtp`, and the configured secret (or test default). Other containers on the Compose network use `postal-smtp:25`.

**This is a temporary Development-mode test, not a public SMTP service.** The job tears down the runner and containers when finished. Postal accepts test messages but does not deliver them to real recipients. The seeded sender domain is verified only inside the disposable test database.

For full steps and troubleshooting, see [HOWTO.md](HOWTO.md). For permanent hosting, domain and DNS setup, see the [Postal installation guide](https://docs.postalserver.io/getting-started).

## Local test

```bash
docker compose -f docker-compose.smtp.yml up -d --build
python3 script/test_smtp_client.py
docker compose -f docker-compose.smtp.yml down
```

Defaults and the checked-in signing key are **for isolated tests only**, not production. TLS is disabled in this test setup. To use a custom password locally, set `POSTAL_CI_CREDENTIAL_KEY` before starting Compose and set `SMTP_PASSWORD` to the same value for the Python test.

## Credits

OryvexSMTP is based on [Postal](https://github.com/postalserver/postal), an open-source mail platform. Postal's documentation is at [docs.postalserver.io](https://docs.postalserver.io/). Original copyright notices and license are retained in [MIT-LICENCE](MIT-LICENCE).
