# Local-only OryvexSMTP portal

The portal submits messages to 127.0.0.1:587 on the runner using server-side SMTP credentials. It does not offer external relay profiles. Loopback SMTP is intentionally unencrypted; never expose it publicly. The TryCloudflare URL is an HTTPS website, not an SMTP hostname.

1. Run the workflow with your real lowercase sender_domain and a test recipient. No GitHub secrets need to be configured.
2. Open the job and expand the "Keep Portal Active" step to see the portal URL, username, and password. The run Summary and "Generate and show credentials for this run" step also show credentials. New passwords are generated for each run.
3. Open the portal link and sign in with username `oryvex` and the displayed portal password.
4. The sender address defaults to test@your-domain; change it to an address at your configured domain if needed. Copy DNS records only when the portal says they are ready.

**Security warning:** Anyone who can read the run logs or summary can obtain these credentials and access the running portal. In a public repository the logs may be visible to the public. Use only for temporary testing in a private repository with trusted log access, never production.

SMTP acceptance means queued, not delivered. Direct delivery requires outbound TCP port 25 and a stable IP with forward/reverse DNS, correct SPF and DKIM. GitHub-hosted runners commonly cannot deliver directly over port 25. Changing to port 587 on a recipient's MX is not a substitute. Use your own suitably configured server/network for direct sending. The Actions runner and its database are temporary; new runs can generate new DKIM keys, so this is not stable production hosting. The supplied CI secrets and test keys must never be used for production.
