#!/usr/bin/env python3
import os
import sys
import time
import smtplib
from email.mime.text import MIMEText

HOST = os.environ.get("SMTP_HOST", "127.0.0.1")
PORT = int(os.environ.get("SMTP_PORT", "587"))
READY_TIMEOUT = int(os.environ.get("SMTP_READY_TIMEOUT", "60"))
USERNAME = os.environ.get("SMTP_USERNAME", "ci/smtp")
PASSWORD = os.environ.get("SMTP_PASSWORD", "postal-ci-key")
FROM_ADDR = os.environ.get("SMTP_FROM", "test@yourdomain.com")
TO_ADDR = os.environ.get("SMTP_TO", "recipient@example.com")


def connect_when_ready(host, port, timeout):
    """Wait for a real SMTP greeting and successful EHLO on configured port."""
    deadline = time.monotonic() + timeout
    attempt = 0
    last_error = None
    ports_to_try = [port]
    if port != 2525:
        ports_to_try.append(2525)

    while time.monotonic() < deadline:
        attempt += 1
        for current_port in ports_to_try:
            client = smtplib.SMTP(timeout=5)
            try:
                code, greeting = client.connect(host, current_port)
                if code != 220:
                    raise smtplib.SMTPConnectError(code, greeting)

                code, response = client.ehlo()
                if not 200 <= code < 300:
                    raise smtplib.SMTPHeloError(code, response)

                print(f"SMTP server is ready on {host}:{current_port} (220 greeting, EHLO {code}).")
                return client
            except (OSError, smtplib.SMTPException) as exc:
                last_error = exc
                client.close()
        
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        print(f"SMTP not ready yet (attempt {attempt}: {last_error}); retrying in 2s...")
        time.sleep(min(2, remaining))

    raise TimeoutError(
        f"SMTP server at {host}:{port} did not complete greeting and EHLO "
        f"within {timeout}s. Last error: {last_error}"
    )


print(f"Connecting to OryvexSMTP server at {HOST}:{PORT}...")
try:
    client = connect_when_ready(HOST, PORT, READY_TIMEOUT)
except (OSError, smtplib.SMTPException, TimeoutError) as exc:
    print(f"\nFAILED: SMTP server did not become ready: {exc}")
    sys.exit(1)

msg = MIMEText("Hello! This is an automated test email sent through OryvexSMTP on GitHub Actions (Port 587/2525).")
msg["Subject"] = "OryvexSMTP GitHub Actions Test Email (Non-25 Port)"
msg["From"] = FROM_ADDR
msg["To"] = TO_ADDR

try:
    print(f"Authenticating as {USERNAME}...")
    client.login(USERNAME, PASSWORD)
    print(f"Sending message from {FROM_ADDR} to {TO_ADDR}...")
    client.send_message(msg)
    print("\nSUCCESS! Email was accepted by OryvexSMTP server!")
except Exception as e:
    print(f"\nFAILED to send email: {e}")
    sys.exit(1)
finally:
    try:
        client.quit()
    except (OSError, smtplib.SMTPException):
        client.close()
