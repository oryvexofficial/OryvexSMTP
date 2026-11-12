# OryvexSMTP local-only workflow

See [LOCAL-SETUP.md](LOCAL-SETUP.md) for the required GitHub secrets, sender domain, portal login and DNS notes.

The portal sends only through the local Postal instance. Its HTTPS TryCloudflare link is a web interface, not an SMTP endpoint. Submission uses loopback port 587 without STARTTLS, while direct delivery to recipients uses port 25. The workflow may accept a message without delivering it: GitHub-hosted runners can block outbound port 25. Use your own host and properly configured DNS and IP for real direct delivery. The runner database is temporary, so generated DKIM keys can change between runs.
