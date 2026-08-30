# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import os
import sys
import time
import base64
import json
import asyncio
import webbrowser
import httpx
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import threading

REDIRECT_PORT = 3000

_AUTH_SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Solar Economy - Authenticated</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #0f1117;
            color: #e2e8f0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
        }
        .card {
            text-align: center;
            padding: 2.5rem 3rem;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
        }
        .check {
            width: 48px; height: 48px;
            margin: 0 auto 1rem;
            border-radius: 50%;
            background: rgba(74, 222, 128, 0.12);
            display: flex; align-items: center; justify-content: center;
        }
        .check svg { width: 24px; height: 24px; }
        h2 { font-size: 1.25rem; font-weight: 600; color: #4ade80; margin-bottom: 0.5rem; }
        p { font-size: 0.875rem; color: #94a3b8; }
    </style>
</head>
<body>
    <div class="card">
        <div class="check">
            <svg viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
        </div>
        <h2>Authentication Successful</h2>
        <p id="msg">This window will close automatically.</p>
    </div>
    <script>
        setTimeout(() => {
            window.close();
            setTimeout(() => {
                document.getElementById('msg').textContent = 'You can close this tab now.';
            }, 300);
        }, 1500);
    </script>
</body>
</html>"""

access_token = None
refresh_token = None
supabase_client = None
supabase_user_uuid = None

operator_jwt: str | None = None
operator_refresh_token: str | None = None
operator_id: int | None = None
operator_jwt_issued_at: float | None = None
operator_jwt_expires_in: int = 3600
operator_discord_id: int | None = None
operator_license_key: str | None = None

_bundle_dir: Path = None


def _console_attached() -> bool:
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def wait_for_exit():
    if _console_attached():
        wait_for_exit()


def _get_bundle_dir() -> Path:
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(sys.executable).parent
    return Path(__file__).parent


def init(bundle_dir: Path, client):
    global _bundle_dir, supabase_client
    _bundle_dir = bundle_dir
    supabase_client = client


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global access_token, refresh_token, supabase_client

        parsed_path = urlparse(self.path)
        query_components = parse_qs(parsed_path.query)

        if 'code' in query_components:
            code = query_components['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = _AUTH_SUCCESS_HTML
            self.wfile.write(html.encode('utf-8'))
            try:
                if supabase_client:
                    response = supabase_client.auth.exchange_code_for_session({"auth_code": code})
                    if response and response.session:
                        access_token = response.session.access_token
                        refresh_token = response.session.refresh_token if hasattr(response.session, 'refresh_token') else None
            except Exception:
                pass

        elif parsed_path.path == '/callback' and 'access_token' in query_components:
            access_token = query_components['access_token'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Token received.')

        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<body style="background:#111;color:#eee;font-family:sans-serif;text-align:center;padding-top:50px;">
    <h2>Authenticating...</h2>
    <script>
        const hash = window.location.hash.substring(1);
        const params = new URLSearchParams(hash);
        const accessToken = params.get('access_token');
        if (accessToken) {
            fetch('/callback?access_token=' + accessToken)
                .then(() => {
                    document.body.innerHTML = '<h2 style="color:#4ade80">Success!</h2><p id="msg">This window will close automatically.</p>';
                    setTimeout(() => {
                        window.close();
                        setTimeout(() => {
                            document.getElementById('msg').textContent = 'You can close this tab now.';
                        }, 300);
                    }, 1500);
                })
                .catch(() => document.body.innerHTML = '<h2 style="color:#f87171">Error sending token to app.</h2>');
        } else {
            document.body.innerHTML = '<h2>No token found in URL.</h2><p>Check your Supabase Redirect settings.</p>';
        }
    </script>
</body>
</html>"""
            self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        pass


def wait_for_token(logger) -> bool:
    import logging
    server = HTTPServer(('localhost', REDIRECT_PORT), OAuthCallbackHandler)
    server.timeout = 0.5
    max_wait = 120
    elapsed = 0
    logger.info("(Press Ctrl+C to cancel)")
    try:
        while access_token is None and elapsed < max_wait:
            try:
                server.handle_request()
            except KeyboardInterrupt:
                raise
            except Exception:
                pass
            elapsed += 1
        if elapsed >= max_wait and access_token is None:
            logger.warning("Authentication timed out.")
            return False
    except KeyboardInterrupt:
        logger.info("Authentication cancelled by user.")
        sys.exit(0)
    return access_token is not None


def run_oauth(logger) -> bool:
    global supabase_user_uuid, operator_discord_id

    print("STEP 1: Discord OAuth Authentication")
    print("-" * 70)
    data = supabase_client.auth.sign_in_with_oauth({
        "provider": "discord",
        "options": {"redirect_to": f"http://localhost:{REDIRECT_PORT}"}
    })
    print("Opening browser...")
    webbrowser.open(data.url)
    print("Waiting for local server to receive token...")
    if not wait_for_token(logger):
        print("\nFailed to capture token.")
        return False
    print("\nToken Captured Successfully!")

    print()
    print("STEP 2: Token Verification")
    print("-" * 70)
    try:
        print("Validating access token...")
        if access_token and refresh_token:
            supabase_client.auth.set_session(access_token, refresh_token)
        elif access_token:
            supabase_client.postgrest.auth(access_token)
        response = supabase_client.auth.get_user(access_token)
        user = response.user
        if user:
            supabase_user_uuid = str(user.id)
            provider_id = (user.user_metadata or {}).get("provider_id")
            if provider_id:
                operator_discord_id = int(provider_id)
        print("Authentication successful.")
    except Exception:
        print("ERROR: Authentication failed.")
        print()
        wait_for_exit()
        sys.exit(1)

    return True


def _edge_function_base() -> str:
    supabase_url = os.getenv("SUPABASE_URL")
    return f"{supabase_url}/functions/v1"


def _decode_jwt_claim(token: str, claim: str):
    payload_b64 = token.split(".")[1]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    return payload.get(claim)


def login_with_license_key(license_key: str = None) -> bool:
    global operator_jwt, operator_refresh_token, operator_id, operator_jwt_issued_at, operator_jwt_expires_in, operator_license_key

    print()
    print("STEP 3: License Validation")
    print("-" * 70)
    license_input = license_key.strip() if license_key else input("Enter License Key: ").strip()
    if not license_input:
        print("ERROR: License key cannot be empty.")
        print()
        wait_for_exit()
        sys.exit(1)

    if not operator_discord_id:
        print("ERROR: No Discord identity available from OAuth session.")
        print()
        wait_for_exit()
        sys.exit(1)

    print("Verifying license key...")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    try:
        resp = httpx.post(
            f"{_edge_function_base()}/login",
            json={
                "license_key": license_input,
                "oauth_discord_id": operator_discord_id,
                "bot_version": os.getenv("BOT_VERSION", ""),
            },
            headers={"Authorization": f"Bearer {anon_key}", "apikey": anon_key},
            timeout=15,
        )
        if resp.status_code == 403 and resp.json().get("error") == "outdated_client":
            min_version = resp.json().get("min_version", "unknown")
            print()
            print("UPDATE REQUIRED")
            print("=" * 70)
            print()
            print(f"This bot version is outdated. Minimum required version: {min_version}")
            print("Please update before continuing.")
            print()
            wait_for_exit()
            sys.exit(1)
        if resp.status_code != 200:
            print()
            print("ACCESS DENIED")
            print("=" * 70)
            print()
            print("Invalid license key.")
            print("Please contact the administrator for support.")
            print()
            wait_for_exit()
            sys.exit(1)

        data = resp.json()
        operator_jwt = data["access_token"]
        operator_refresh_token = data["refresh_token"]
        operator_jwt_expires_in = data.get("expires_in", 3600)
        operator_jwt_issued_at = time.monotonic()
        operator_id = _decode_jwt_claim(operator_jwt, "operator_id")
        operator_license_key = license_input

        print()
        print("=" * 70)
        print(" " * 22 + "LICENSE VERIFIED")
        print("=" * 70)
        print()
        print("Solar Economy is now active.")
        print("All systems operational.")
        print()
        return True
    except Exception:
        print("ERROR: License verification failed.")
        print()
        print("Unable to verify license at this time.")
        print()
        wait_for_exit()
        sys.exit(1)


def login_with_saved_credentials() -> bool:
    global operator_jwt, operator_refresh_token, operator_id, operator_jwt_issued_at, operator_jwt_expires_in, operator_discord_id, operator_license_key

    import services.credential_store as credential_store

    creds = credential_store.load_credentials()
    if not creds:
        return False

    anon_key = os.getenv("SUPABASE_ANON_KEY")
    try:
        resp = httpx.post(
            f"{_edge_function_base()}/login",
            json={
                "license_key": creds["license_key"],
                "oauth_discord_id": creds["discord_id"],
                "bot_version": os.getenv("BOT_VERSION", ""),
            },
            headers={"Authorization": f"Bearer {anon_key}", "apikey": anon_key},
            timeout=15,
        )
        if resp.status_code != 200:
            credential_store.clear_credentials()
            return False

        data = resp.json()
        operator_jwt = data["access_token"]
        operator_refresh_token = data["refresh_token"]
        operator_jwt_expires_in = data.get("expires_in", 3600)
        operator_jwt_issued_at = time.monotonic()
        operator_id = _decode_jwt_claim(operator_jwt, "operator_id")
        operator_discord_id = creds["discord_id"]
        operator_license_key = creds["license_key"]
        return True
    except Exception:
        credential_store.clear_credentials()
        return False


async def fetch_operator_assets() -> dict | None:
    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{supabase_url}/rest/v1/operator_assets",
            headers={
                "Authorization": f"Bearer {operator_jwt}",
                "apikey": anon_key,
            },
            params={"select": "api_token,bot_config,database_url,firebase_api_key"},
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None


async def refresh_loop(logger):
    global operator_jwt, operator_refresh_token, operator_jwt_issued_at, operator_jwt_expires_in

    while True:
        elapsed = time.monotonic() - operator_jwt_issued_at
        remaining = operator_jwt_expires_in - elapsed
        sleep_for = max(remaining - 300, 5)
        await asyncio.sleep(sleep_for)

        try:
            anon_key = os.getenv("SUPABASE_ANON_KEY")
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_edge_function_base()}/refresh",
                    json={"refresh_token": operator_refresh_token},
                    headers={"Authorization": f"Bearer {anon_key}", "apikey": anon_key},
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                operator_jwt = data["access_token"]
                operator_refresh_token = data["refresh_token"]
                operator_jwt_expires_in = data.get("expires_in", 3600)
                operator_jwt_issued_at = time.monotonic()
        except Exception:
            logger.error("Operator token refresh failed — bot auth may expire soon.")
            await asyncio.sleep(30)
