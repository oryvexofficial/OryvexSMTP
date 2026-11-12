# HOWTO: OryvexSMTP & Web Portal on GitHub Actions

## Overview

This project provides a full mail server and testing dashboard running on **GitHub Actions**, exposed to the internet via **TryCloudflare**, with support for:
1. **Local OryvexSMTP Server**: Listening on port `2525`.
2. **Multi-Port Outbound Delivery**: Supports Port `587` (STARTTLS) and Port `465` (SSL) to deliver real emails to your Gmail inbox (`faketype3@gmail.com`).
3. **Cloudflare Sender Domain Setup**: Automated SPF, DKIM, DMARC, and Return-Path DNS generation for your domain (e.g., `yourdomain.com`).
4. **Live Server Mode**: Set to `Live` so emails are dispatched instead of held.

---

## Why Outbound Port 25 is Blocked on GitHub Actions

GitHub Actions runs on Microsoft Azure virtual machines. Azure and GitHub intentionally block all outgoing traffic on **TCP Port 25** to stop spam.

To send real emails to Gmail or other mail providers from GitHub Actions:
- **Port 587 (STARTTLS)**: Allowed by GitHub Actions.
- **Port 465 (SMTPS / SSL)**: Allowed by GitHub Actions.
- Use your SMTP relay (e.g., Gmail App Password, Brevo, SendGrid, Mailgun, or your custom mail relay).

---

## 1. Cloudflare DNS Setup for Your Sender Domain

In your **Cloudflare Dashboard** under your domain (e.g. `yourdomain.com`):
Go to **DNS → Records** and add the following (ensure Proxy status is **DNS only / grey cloud**):

| Type | Name | Content / Target | Proxy Status |
| :--- | :--- | :--- | :--- |
| **TXT** | `@` | `v=spf1 include:_spf.mx.cloudflare.net ~all` | DNS only |
| **TXT** | `postal._domainkey` | `v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC3r...` | DNS only |
| **TXT** | `_dmarc` | `v=DMARC1; p=none; rua=mailto:postmaster@yourdomain.com` | DNS only |
| **CNAME** | `psrp` | `rp.postal.example.com` | DNS only |
| **MX** | `@` | `mail.yourdomain.com` (Priority: 10) | DNS only |

*(The Web Portal will generate these exact records with copy buttons for your specific domain!)*

---

## 2. Running on GitHub Actions

1. Commit and push this project to your GitHub repository:
   ```bash
   git add .
   git commit -m "Full GitHub Actions multi-port and Cloudflare setup"
   git push origin main
   ```
2. Go to the **Actions** tab in GitHub.
3. Select **OryvexSMTP Service & Web Portal**.
4. Click **Run workflow**:
   - **Server Mode**: `Live`
   - **Sender Domain**: `yourdomain.com` (or your domain)
   - **Tunnel Duration**: `30` (minutes to keep web portal online)
   - **Test Recipient**: `faketype3@gmail.com`
5. Click **Run workflow**.

---

## 3. Using the Web Portal & Delivering to Your Inbox

1. In the GitHub Actions run, click the **Summary** tab to find your public TryCloudflare URL:
   `https://<random-id>.trycloudflare.com`
2. Open the URL in your browser.
3. In the Web Portal:
   - To send via **Gmail Relay (Port 587)**:
     - Click the **📮 Gmail Relay (Port 587)** preset.
     - Enter your Gmail address and Google **App Password** (create one at: *Google Account → Security → 2-Step Verification → App Passwords*).
     - Click **🚀 Send Test Email**.
     - The email will land directly in your Gmail inbox!
   - To send via **Brevo** or **SendGrid**:
     - Click the **Brevo** or **SendGrid** preset.
     - Enter your API Key as password.
     - Click **🚀 Send Test Email**.
   - To test the **Local OryvexSMTP**:
     - Click **🖥️ Local OryvexSMTP (Port 2525)** to inspect the local Postal processing pipeline.
4. Watch the **SMTP Live Transcript** in real time as the SMTP handshake negotiates and completes.
