"""
Playwright Dev.to Login Script

Run this to create the browser session for Dev.to.
Opens a visible browser for manual login, then saves the session.
"""
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

def setup_devto_login():
    print("🦕 Playwright Dev.to Login Setup")
    print("=" * 50)
    print("A browser window will open.")
    print("1. Login to Dev.to normally (Email, GitHub, Twitter, etc.)")
    print("2. Wait until you see your feed/home page")
    print("=" * 50)
    # Point to project root/browser_state
    project_root = Path(__file__).resolve().parent.parent
    session_path = project_root / "browser_state"
    session_path.mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/Sao_Paulo'
        )
        
        page = context.new_page()
        
        print("\n🌐 Opening Dev.to Enter options...")
        page.goto('https://dev.to/enter')
        
        print("⏳ Waiting for you to login...")
        print("   (The script will detect when you're logged in)")
        
        # Wait for user to confirm login
        print("\n👉 Please log in to Dev.to in the browser.")
        print("   Once you see your home feed or profile, come back here.")
        input("✅ Press Enter here when you are logged in successfully...")
        
        # Optional: We can still try to verify, but we trust the user now.
        if page.is_visible('#write-link') or page.is_visible('.crayons-avatar'):
            print("   (Auto-detected login elements!)")
        else:
            print("   (Could not strict-detect login elements, but saving anyway based on your confirmation)")
        
        # Save browser state
        context.storage_state(path=str(session_path / "state_devto.json"))
        print(f"\n💾 Session saved to: {session_path}/state_devto.json")
        
        browser.close()
        
    print("\n🎉 Success! You can now use the Dev.to Client.")
    return True

if __name__ == "__main__":
    setup_devto_login()
