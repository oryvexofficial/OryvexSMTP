#!/usr/bin/env python3
"""
OryvexSMTP Web Portal
A lightweight, dependency-free web interface to monitor and test-send emails
through an OryvexSMTP server instance or external SMTP relays (Port 587 / 465).
"""

import os
import sys
import json
import time
import ssl
import socket
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Configuration with environment defaults
SMTP_HOST = os.environ.get("SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "ci/smtp")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "postal-ci-key")
SMTP_FROM = os.environ.get("SMTP_FROM", "test@postal-ci.local")
DEFAULT_TO = os.environ.get("DEFAULT_TO", "faketype3@gmail.com")
WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))
DNS_FILE_PATH = os.environ.get("DNS_FILE_PATH", os.path.join(os.path.dirname(__file__), "..", "docker", "ci-config", "dns_records.json"))

# Sent history storage (in-memory)
SENT_HISTORY = []
MAX_HISTORY = 50


def check_smtp_health(host=SMTP_HOST, port=SMTP_PORT, timeout=3):
    """Check if target SMTP server responds to greeting and EHLO."""
    transcript = []
    try:
        start_time = time.time()
        client = smtplib.SMTP(timeout=timeout)
        code, banner = client.connect(host, port)
        transcript.append(f"Connected to {host}:{port} -> Code {code}: {banner.decode(errors='replace').strip()}")
        code, helo_resp = client.ehlo()
        transcript.append(f"EHLO -> Code {code}: {helo_resp.decode(errors='replace').strip()}")
        client.quit()
        latency_ms = round((time.time() - start_time) * 1000, 1)
        return True, "SMTP server is online and ready", transcript, latency_ms
    except Exception as exc:
        return False, str(exc), transcript, None


def send_smtp_email(to_addr, subject, body, from_addr=SMTP_FROM,
                    host=SMTP_HOST, port=SMTP_PORT,
                    username=None, password=None,
                    ssl_mode="auto", is_html=False):
    """
    Send an email via SMTP supporting:
    - Standard SMTP (Port 25, 2525)
    - STARTTLS (Port 587, 25)
    - SMTPS / Direct SSL (Port 465)
    """
    transcript = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if not to_addr:
        raise ValueError("Recipient address is required")

    transcript.append(f"[{timestamp}] Connecting to SMTP server at {host}:{port} (SSL mode: {ssl_mode})...")

    client = None
    try:
        is_direct_ssl = (port == 465 or ssl_mode == "ssl")
        tls_context = ssl.create_default_context()

        if is_direct_ssl:
            transcript.append(f"-> Establishing direct SSL/TLS session...")
            client = smtplib.SMTP_SSL(host, port, context=tls_context, timeout=15)
        else:
            client = smtplib.SMTP(timeout=15)
            code, greeting = client.connect(host, port)
            transcript.append(f"<- {code} {greeting.decode(errors='replace').strip()}")

        code, ehlo_resp = client.ehlo()
        transcript.append(f"-> EHLO client.local")
        transcript.append(f"<- {code} {ehlo_resp.decode(errors='replace').strip()}")

        if not is_direct_ssl and (ssl_mode in ("starttls", "auto") or port == 587):
            if client.has_extn("STARTTLS") or port == 587:
                transcript.append(f"-> STARTTLS")
                client.starttls(context=tls_context)
                code, ehlo_resp = client.ehlo()
                transcript.append(f"<- TLS Established. New EHLO: {code}")
            elif ssl_mode == "starttls":
                raise smtplib.SMTPException("Server does not support STARTTLS")

        if username and password:
            transcript.append(f"-> AUTH (User: {username})")
            code, auth_resp = client.login(username, password)
            transcript.append(f"<- {code} {auth_resp.decode(errors='replace').strip()}")

        msg = MIMEMultipart("alternative") if is_html else MIMEText(body, "plain", "utf-8")
        if is_html:
            msg.attach(MIMEText(body, "html", "utf-8"))
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        msg["X-Mailer"] = "OryvexSMTP-WebPortal/1.1"

        transcript.append(f"-> MAIL FROM:<{from_addr}>")
        transcript.append(f"-> RCPT TO:<{to_addr}>")
        transcript.append(f"-> DATA ({len(msg.as_string())} bytes)")

        send_errors = client.send_message(msg)
        if send_errors:
            transcript.append(f"<- Partial delivery rejection: {send_errors}")
            raise smtplib.SMTPResponseException(550, f"Delivery rejected: {send_errors}")

        transcript.append(f"<- 250 2.0.0 Message successfully accepted for delivery")

        history_entry = {
            "timestamp": timestamp,
            "to": to_addr,
            "from": from_addr,
            "subject": subject,
            "status": "Accepted",
            "host": f"{host}:{port}",
            "latency": "OK"
        }
        SENT_HISTORY.insert(0, history_entry)
        if len(SENT_HISTORY) > MAX_HISTORY:
            SENT_HISTORY.pop()

        return True, "Email successfully queued/accepted for delivery!", transcript

    except Exception as e:
        error_msg = f"SMTP Error: {str(e)}"
        transcript.append(f"<- ERROR: {error_msg}")
        history_entry = {
            "timestamp": timestamp,
            "to": to_addr,
            "from": from_addr,
            "subject": subject,
            "status": f"Failed: {str(e)[:40]}",
            "host": f"{host}:{port}",
            "latency": "ERR"
        }
        SENT_HISTORY.insert(0, history_entry)
        return False, error_msg, transcript
    finally:
        if client:
            try:
                transcript.append(f"-> QUIT")
                client.quit()
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass


def get_cloudflare_dns_guide(domain_name="yourdomain.com"):
    """Generate exact Cloudflare DNS records for a given sender domain."""
    dns_file = DNS_FILE_PATH
    if os.path.exists(dns_file):
        try:
            with open(dns_file, "r") as f:
                data = json.load(f)
                return data
        except Exception:
            pass

    clean_domain = domain_name.strip().lower()
    return {
        "domain": clean_domain,
        "spf_record": f"v=spf1 include:_spf.mx.cloudflare.net ~all",
        "dkim_name": f"postal._domainkey.{clean_domain}",
        "dkim_record": "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC3r...",
        "dmarc_name": f"_dmarc.{clean_domain}",
        "dmarc_record": f"v=DMARC1; p=none; rua=mailto:postmaster@{clean_domain}",
        "return_path_domain": f"psrp.{clean_domain}",
        "return_path_target": "rp.postal.example.com"
    }


class OryvexHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        try:
            msg = format % args
        except Exception:
            msg = " ".join(str(a) for a in args)
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")

    def send_json_response(self, status_code, data):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
            if not os.path.exists(template_path):
                template_path = os.path.join(os.path.dirname(__file__), "index.html")

            if os.path.exists(template_path):
                size = os.path.getsize(template_path)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(size))
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
        elif path in ("/health", "/api/status", "/api/history", "/api/dns-records"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
            if not os.path.exists(template_path):
                template_path = os.path.join(os.path.dirname(__file__), "index.html")

            if os.path.exists(template_path):
                with open(template_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"<h1>404: Template not found</h1>")

        elif path == "/api/status":
            online, message, transcript, latency = check_smtp_health()
            self.send_json_response(200, {
                "online": online,
                "message": message,
                "transcript": transcript,
                "latency_ms": latency,
                "smtp_host": SMTP_HOST,
                "smtp_port": SMTP_PORT,
                "smtp_from": SMTP_FROM,
                "smtp_username": SMTP_USERNAME,
                "default_to": DEFAULT_TO
            })

        elif path == "/api/history":
            self.send_json_response(200, {
                "history": SENT_HISTORY
            })

        elif path == "/api/dns-records":
            domain = query.get("domain", ["yourdomain.com"])[0]
            dns_info = get_cloudflare_dns_guide(domain)
            self.send_json_response(200, dns_info)

        elif path == "/health":
            self.send_json_response(200, {"status": "ok", "app": "OryvexSMTP-Web"})

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/send":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_json_response(400, {"success": False, "message": "Empty request body"})
                return

            body_data = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body_data)
            except Exception as e:
                self.send_json_response(400, {"success": False, "message": f"Invalid JSON: {e}"})
                return

            to_addr = payload.get("to") or DEFAULT_TO
            from_addr = payload.get("from") or SMTP_FROM
            subject = payload.get("subject", "Test Email from OryvexSMTP")
            body = payload.get("body", "This is a test email sent from the OryvexSMTP Web Portal.")
            host = payload.get("host") or SMTP_HOST
            port = int(payload.get("port") or SMTP_PORT)
            username = payload.get("username")
            password = payload.get("password")
            ssl_mode = payload.get("ssl_mode", "auto")
            is_html = bool(payload.get("is_html", False))

            success, message, transcript = send_smtp_email(
                to_addr=to_addr,
                subject=subject,
                body=body,
                from_addr=from_addr,
                host=host,
                port=port,
                username=username,
                password=password,
                ssl_mode=ssl_mode,
                is_html=is_html
            )

            status_code = 200 if success else 500
            self.send_json_response(status_code, {
                "success": success,
                "message": message,
                "transcript": transcript,
                "to": to_addr,
                "subject": subject
            })

        elif path == "/api/check":
            content_length = int(self.headers.get("Content-Length", 0))
            payload = {}
            if content_length > 0:
                try:
                    payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except Exception:
                    pass

            host = payload.get("host") or SMTP_HOST
            port = int(payload.get("port") or SMTP_PORT)
            online, message, transcript, latency = check_smtp_health(host, port)
            self.send_json_response(200, {
                "online": online,
                "message": message,
                "transcript": transcript,
                "latency_ms": latency
            })
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


def run_server():
    server_address = (WEB_HOST, WEB_PORT)
    httpd = ThreadingHTTPServer(server_address, OryvexHTTPHandler)
    print(f"==================================================")
    print(f"OryvexSMTP Web Portal running on http://{WEB_HOST}:{WEB_PORT}")
    print(f"Target SMTP Server: {SMTP_HOST}:{SMTP_PORT}")
    print(f"Default recipient: {DEFAULT_TO}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down web portal...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
