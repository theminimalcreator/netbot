import sys
import os
import traceback
from urllib.parse import unquote
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagrapi import Client
from config.settings import settings

def manual_session_import():
    print("🍪 Manual Session Import")
    print("--------------------------------------------------")
    print("Instructions:")
    print("1. Open Instagram.com in your browser and log in.")
    print("2. Open Developer Tools (F12) -> Application/Storage -> Cookies.")
    print("3. Find the cookie named 'sessionid'.")
    print("--------------------------------------------------")
    
    session_id_input = input("Paste your 'sessionid' here: ").strip()
    
    if not session_id_input:
        print("❌ No session ID provided.")
        return

    # Automatically decode if the user pasted a URL-encoded string (common from copying from DevTools)
    session_id = unquote(session_id_input)
    if session_id != session_id_input:
        print(f"ℹ️  Detected URL-encoded session ID. Decoded to: {session_id[:20]}...")

    cl = Client()
    
    # Setup device to match the bot's configuration
    cl.set_device(settings.DEVICE_SETTINGS)
    cl.set_locale("pt_BR")
    cl.set_country("BR")
    cl.set_timezone_offset(-3 * 3600)
    
    try:
        print("🔄 Verifying session...")
        cl.login_by_sessionid(session_id)
        
        print("✅ Login Successful!")
        
        session_path = Path("session.json")
        cl.dump_settings(session_path)
        
        print(f"🎉 Session saved to {session_path.absolute()}")
        print("You can now run 'python3 main.py'")
        
    except Exception as e:
        print(f"❌ Failed to login with this session ID: {e}")
        print("\n🔍 Full Traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    manual_session_import()
