"""
Playwright Threads Login Script

Run this to create the browser session for Threads.
Opens a visible browser for manual login, then saves the session.
"""
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

def setup_threads_login():
    print("🧵 Playwright Threads Login Setup")
    print("=" * 50)
    print("A browser window will open.")
    print("1. Login to Threads normally (e.g. via Instagram)")
    print("2. Complete any challenges")
    print("3. Wait until you see your feed")
    print("=" * 50)
    input("Press Enter to start...")
    
    session_path = Path(__file__).resolve().parent.parent / "browser_state"
    session_path.mkdir(exist_ok=True, parents=True)
    
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
        
        print("\n🌐 Opening Threads.net...")
        page.goto('https://www.threads.net/login')
        
        print("⏳ Waiting for you to login...")
        print("   (The script will detect when you're logged in)")
        
        try:
            # Wait for Home icon or feed
            # Threads selectors are dynamic but 'svg[aria-label="Home"]' is consistent with Instagram family
            page.wait_for_selector(
                'svg[aria-label="Home"], a[href="/"] svg[aria-label="Home"]',
                timeout=300000  # 5 minutes
            )
            print("\n✅ Login detected!")
            
            # Save browser state only on success
            context.storage_state(path=str(session_path / "state_threads.json"))
            print(f"\n💾 Session saved to: {session_path}/state_threads.json")
            
        except Exception as e:
            print(f"\n⚠️ Timeout or error: {e}")
            browser.close()
            return False
        
        browser.close()
        
    print("\n🎉 Success! You can now use the Threads Client.")
    return True

if __name__ == "__main__":
    success = setup_threads_login()
    if not success:
        sys.exit(1)
