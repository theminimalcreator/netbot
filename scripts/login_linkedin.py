"""
LinkedIn Login Script — OAuth 2.0 + Playwright Session

1. Opens browser to LinkedIn OAuth consent page (Playwright)
2. Spins up localhost:8585 to capture the redirect with auth code
3. Exchanges code for access_token (API)
4. Saves:
   - browser_state/linkedin_token.json  (API token)
   - browser_state/state_linkedin.json  (Playwright cookies/storage)

Usage:
    python scripts/login_linkedin.py
"""
import sys
import os
import json
import time
import secrets
import threading
import requests
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from playwright.sync_api import sync_playwright

# Configuration
PORT = 8585
REDIRECT_URI = f"http://localhost:{PORT}/callback"
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
SCOPES = "openid profile email w_member_social"

# Global state to capture code
auth_code = None
auth_event = threading.Event()

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed_url = urlparse(self.path)
        
        if parsed_url.path == "/callback":
            query_params = parse_qs(parsed_url.query)
            
            if 'code' in query_params:
                auth_code = query_params['code'][0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">Login Successful!</h1>
                    <p>You can close this tab and return to the terminal.</p>
                </body>
                </html>
                """)
                auth_event.set()
            else:
                self.send_response(400)
                self.wfile.write(b"Error: Missing code parameter")
        else:
            self.send_response(404)
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        return # Silence server logs

def start_server():
    server = HTTPServer(('localhost', PORT), OAuthHandler)
    server.timeout = 1  # check for shutdown every second
    while not auth_event.is_set():
        server.handle_request()

def setup_linkedin_login():
    print("👔 LinkedIn Login Setup (OAuth + Playwright)")
    print("=" * 50)
    
    if not settings.LINKEDIN_CLIENT_ID or settings.LINKEDIN_CLIENT_ID == "your_client_id":
        print("❌ Error: LINKEDIN_CLIENT_ID is not set in .env")
        return False

    session_dir = Path(__file__).resolve().parent.parent / "browser_state"
    session_dir.mkdir(exist_ok=True)
    
    token_path = session_dir / "linkedin_token.json"
    state_path = session_dir / "state_linkedin.json"

    # 1. Start Local Server
    print(f"📡 Starting local listener on port {PORT}...")
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()

    # 2. Build Auth URL
    state = secrets.token_urlsafe(16)
    login_url = (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={settings.LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
        f"&scope={SCOPES}"
    )

    print("\n🌐 Launching browser for login...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # 3. User Login
        print("👉 Please log in to LinkedIn in the browser window.")
        page.goto(login_url)

        # Wait for the callback to be hit (server thread sets the event)
        print("⏳ Waiting for callback capture...")
        
        # We wait up to 5 minutes
        if auth_event.wait(timeout=300):
            print("\n✅ OAuth Code captured!")
            time.sleep(2) # Let the success page render
            
            # 4. Save Playwright Session
            context.storage_state(path=str(state_path))
            print(f"💾 Browser state saved to: {state_path}")
            
            browser.close()
            
            # 5. Exchange Code for Token
            print("🔄 Exchanging code for access token...")
            if not auth_code:
                print("❌ Error: Code was not captured correctly.")
                return False

            payload = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": settings.LINKEDIN_CLIENT_ID,
                "client_secret": settings.LINKEDIN_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI
            }
            
            try:
                resp = requests.post(TOKEN_URL, data=payload, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    data["obtained_at"] = int(time.time())
                    
                    with open(token_path, "w") as f:
                        json.dump(data, f, indent=2)
                        
                    print(f"💾 API Token saved to: {token_path}")
                    print(f"   Expires in: {data.get('expires_in')} seconds")
                    
                    print("\n🎉 LinkedIn Login Successful!")
                    return True
                else:
                    print(f"❌ Token Exchange Failed: {resp.status_code}")
                    print(resp.text)
                    return False
            except Exception as e:
                print(f"❌ Error during token exchange: {e}")
                return False

        else:
            print("\n❌ Timeout waiting for login.")
            browser.close()
            return False

if __name__ == "__main__":
    setup_linkedin_login()
