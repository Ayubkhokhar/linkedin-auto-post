"""
token_helper.py — Run this ONCE locally to get your LinkedIn OAuth tokens.

Usage:
    python scripts/token_helper.py

This will:
1. Open LinkedIn OAuth in your browser
2. Listen for the redirect callback
3. Exchange the auth code for tokens
4. Print the tokens to copy into GitHub Secrets

Requirements:
    pip install requests python-dotenv
"""

import os
import sys
import json
import secrets
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import requests
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ──────────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
REDIRECT_URI  = "http://localhost:8765/callback"
SCOPES        = ["openid", "profile", "email", "w_member_social"]
AUTH_URL      = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL     = "https://www.linkedin.com/oauth/v2/accessToken"
# ─────────────────────────────────────────────────────────────────────────────

auth_code_received = None
state_value = secrets.token_urlsafe(16)


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code_received
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code_received = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;text-align:center;padding-top:60px;background:#0f0f1a;color:#fff">
                <h2 style="color:#7c3aed">Authorization Successful!</h2>
                <p>You can close this tab and return to your terminal.</p>
                </body></html>
            """)
        else:
            error = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body>Error: {error}</body></html>".encode())

    def log_message(self, format, *args):
        pass  # suppress server logs


def start_local_server():
    server = HTTPServer(("localhost", 8765), CallbackHandler)
    server.handle_request()
    server.server_close()


def get_user_urn(access_token: str) -> str:
    """Fetch the LinkedIn member URN (needed for posting)."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": "202401",
    }
    resp = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    if resp.ok:
        data = resp.json()
        sub = data.get("sub", "")
        return f"urn:li:person:{sub}"
    return ""


def main():
    print("\n" + "="*60)
    print("  LinkedIn Token Helper — One-Time Setup")
    print("="*60)

    if not CLIENT_ID or not CLIENT_SECRET:
        print("\n[ERROR] Missing credentials. Create a .env file with:")
        print("  LINKEDIN_CLIENT_ID=your_client_id")
        print("  LINKEDIN_CLIENT_SECRET=your_client_secret\n")
        sys.exit(1)

    # Build OAuth URL
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state_value,
        "scope": " ".join(SCOPES),
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n[1/4] Starting local callback server on port 8765...")
    server_thread = Thread(target=start_local_server)
    server_thread.start()

    print("[2/4] Opening LinkedIn OAuth in your browser...")
    print(f"      If it doesn't open, visit:\n      {url}\n")
    webbrowser.open(url)

    print("[3/4] Waiting for authorization (please log in and approve)...")
    server_thread.join(timeout=600)

    if not auth_code_received:
        print("\n[ERROR] No auth code received within 2 minutes. Please try again.")
        sys.exit(1)

    print("[4/4] Exchanging authorization code for tokens...")
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": auth_code_received,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })

    if not resp.ok:
        print(f"\n[ERROR] Token exchange failed: {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    token_data = resp.json()
    access_token  = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in    = token_data.get("expires_in", 5183999)

    user_urn = get_user_urn(access_token)

    print("\n" + "="*60)
    print("  SUCCESS! Copy these values into GitHub Secrets:")
    print("="*60)
    print(f"\n  LINKEDIN_CLIENT_ID      = {CLIENT_ID}")
    print(f"  LINKEDIN_CLIENT_SECRET  = {CLIENT_SECRET}")
    print(f"  LINKEDIN_ACCESS_TOKEN   = {access_token}")
    print(f"  LINKEDIN_REFRESH_TOKEN  = {refresh_token or '(none — token valid for ~60 days)'}")
    print(f"  LINKEDIN_USER_URN       = {user_urn}")
    print(f"\n  Token expires in: {expires_in // 86400} days")

    # Save locally as backup
    out = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_urn": user_urn,
        "expires_in_seconds": expires_in,
    }
    with open("data/tokens_backup.json", "w") as f:
        json.dump(out, f, indent=2)

    print("\n  Backup saved to data/tokens_backup.json")
    print("  (Do NOT commit this file — it's in .gitignore)\n")
    print("  Next step: Add all secrets to:")
    print("  GitHub repo → Settings → Secrets and variables → Actions\n")


if __name__ == "__main__":
    main()
