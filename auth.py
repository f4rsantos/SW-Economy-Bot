import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import threading

REDIRECT_PORT = 3000

access_token = None
refresh_token = None
supabase_client = None
supabase_user_uuid = None

_bundle_dir: Path = None


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
            html = (_bundle_dir / "assets" / "auth_success.html").read_text(encoding='utf-8')
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
                    document.body.innerHTML = '<h2 style="color:#4ade80">Success!</h2>';
                    setTimeout(() => window.close(), 1500);
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
    global supabase_user_uuid

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
        print("Authentication successful.")
    except Exception:
        print("ERROR: Authentication failed.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    return True


def verify_license() -> bool:
    print()
    print("STEP 3: License Validation")
    print("-" * 70)
    license_input = input("Enter License Key: ").strip()
    if not license_input:
        print("ERROR: License key cannot be empty.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)

    print("Verifying license key...")
    try:
        rpc_response = supabase_client.rpc("verify_license", {"p_input_key": license_input}).execute()
        is_valid = rpc_response.data
        print()
        if is_valid:
            print("=" * 70)
            print(" " * 22 + "LICENSE VERIFIED")
            print("=" * 70)
            print()
            print("Solar Economy is now active.")
            print("All systems operational.")
            print()
            return True
        else:
            print("ACCESS DENIED")
            print("=" * 70)
            print()
            print("Invalid license key.")
            print("Please contact the administrator for support.")
            print()
            input("Press Enter to exit...")
            sys.exit(1)
    except Exception as e:
        print("ERROR: License verification failed.")
        print()
        error_msg = str(e).lower()
        if "function" in error_msg and "does not exist" in error_msg:
            print("Please contact the administrator.")
        elif "no rows" in error_msg or "null" in error_msg:
            print("No license found for this account.")
            print("Please contact the administrator to obtain a license.")
        else:
            print("Unable to verify license at this time.")
        print()
        input("Press Enter to exit...")
        sys.exit(1)
