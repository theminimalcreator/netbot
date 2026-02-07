"""
Playwright Login Setup Script

Run this FIRST to create the browser session.
Opens a visible browser for manual login, then saves the session.
"""
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright


def setup_login():
    print("🎭 Playwright Instagram Login Setup")
    print("=" * 50)
    print("A browser window will open.")
    print("1. Login to Instagram normally")
    print("2. Complete any challenges (SMS, email, captcha)")
    print("3. Wait until you see your feed")
    print("=" * 50)
    input("Press Enter to start...")
    
    session_path = Path("browser_state")
    session_path.mkdir(exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='pt-BR',
            timezone_id='America/Sao_Paulo'
        )
        
        page = context.new_page()
        
        print("\n🌐 Opening Instagram...")
        page.goto('https://www.instagram.com/accounts/login/')
        
        print("⏳ Waiting for you to login...")
        print("   (The script will detect when you're logged in)")
        
        try:
            page.wait_for_selector(
                'svg[aria-label="Home"], svg[aria-label="Página inicial"], a[href="/direct/inbox/"]',
                timeout=300000  # 5 minutes
            )
            print("\n✅ Login detected!")
            
        except Exception as e:
            print(f"\n⚠️ Timeout or error: {e}")
        
        # Save browser state
        context.storage_state(path=str(session_path / "state.json"))
        print(f"\n💾 Session saved to: {session_path}/state.json")
        
        browser.close()
        
    print("\n🎉 Success! You can now run: python main.py")
    return True


if __name__ == "__main__":
    setup_login()
