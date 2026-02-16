#!/usr/bin/env python3
"""
Interactive LinkedIn Feed Test Script v2
Finds the ACTUAL scroll container (LinkedIn uses a nested div, not window scroll).
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_FILE = BASE_DIR / "browser_state" / "state_linkedin.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def count_posts(page):
    return page.evaluate("() => document.querySelectorAll('[data-view-name=\"feed-full-update\"]').length")

def main():
    print("=" * 60)
    print("🔍 LinkedIn Feed Test Script v2 — Finding scroll container")
    print("=" * 60)
    
    if not STATE_FILE.exists():
        print(f"❌ Session file not found: {STATE_FILE}")
        return
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            storage_state=str(STATE_FILE),
            viewport={'width': 1280, 'height': 800},
            user_agent=USER_AGENT,
            locale='en-US'
        )
        
        page = context.new_page()
        
        # --- STEP 1: Load feed ---
        print("\n📄 STEP 1: Loading LinkedIn feed...")
        page.goto("https://www.linkedin.com/feed/", timeout=30000)
        page.wait_for_load_state("domcontentloaded")
        time.sleep(5)
        
        posts = count_posts(page)
        print(f"   Posts in DOM: {posts}")
        print(f"   URL: {page.url}")
        
        # --- STEP 2: Find the scroll container ---
        print("\n🔎 STEP 2: Searching for the actual scroll container...")
        
        scroll_info = page.evaluate("""() => {
            // Find all elements with overflow-y: auto or scroll that have significant height
            const results = [];
            const allElements = document.querySelectorAll('*');
            
            for (const el of allElements) {
                const style = window.getComputedStyle(el);
                const overflowY = style.overflowY;
                
                if (overflowY === 'auto' || overflowY === 'scroll') {
                    const rect = el.getBoundingClientRect();
                    if (rect.height >= 400 && el.scrollHeight > rect.height) {
                        results.push({
                            tag: el.tagName,
                            id: el.id || '',
                            classes: el.className.substring(0, 100),
                            overflowY: overflowY,
                            scrollHeight: el.scrollHeight,
                            clientHeight: Math.round(rect.height),
                            scrollTop: el.scrollTop,
                            scrollable: el.scrollHeight - rect.height,
                            hasFeeds: el.querySelectorAll('[data-view-name="feed-full-update"]').length
                        });
                    }
                }
            }
            
            // Also check document.body and html
            results.push({
                tag: 'WINDOW',
                id: 'window',
                classes: '',
                overflowY: 'n/a',
                scrollHeight: document.body.scrollHeight,
                clientHeight: window.innerHeight,
                scrollTop: window.scrollY,
                scrollable: document.body.scrollHeight - window.innerHeight,
                hasFeeds: -1
            });
            
            return results;
        }""")
        
        print(f"\n   Found {len(scroll_info)} scrollable containers:")
        for i, info in enumerate(scroll_info):
            marker = "⭐" if info['hasFeeds'] > 0 else "  "
            print(f"   {marker} [{i}] <{info['tag']}> id='{info['id']}' classes='{info['classes'][:60]}'")
            print(f"        overflow-y: {info['overflowY']}, scrollHeight: {info['scrollHeight']}, "
                  f"clientHeight: {info['clientHeight']}, scrollable: {info['scrollable']}px, "
                  f"feeds inside: {info['hasFeeds']}")
        
        input("\n👆 Look at the ⭐ markers — those contain feed posts. Press ENTER to test scrolling them...\n")
        
        # --- STEP 3: Try scrolling the right container ---
        # Find the container with the most feed posts
        best = None
        for info in scroll_info:
            if info['hasFeeds'] > 0 and (best is None or info['hasFeeds'] > best['hasFeeds']):
                best = info
        
        if not best:
            print("❌ No scrollable container with feed posts found!")
            input("Press ENTER to close...")
            browser.close()
            return
        
        print(f"\n📜 STEP 3: Scrolling the best container: <{best['tag']}> (id='{best['id']}', classes='{best['classes'][:50]}')")
        
        # Build a JS selector for this container
        if best['id']:
            container_selector = f"#{best['id']}"
        else:
            # Use classes — take the first class
            first_class = best['classes'].split()[0] if best['classes'] else ''
            container_selector = f".{first_class}" if first_class else best['tag'].lower()
        
        print(f"   Using selector: '{container_selector}'")
        
        for i in range(15):
            # Scroll the container
            prev = page.evaluate(f"""() => {{
                const el = document.querySelector('{container_selector}');
                if (!el) return null;
                const prev = el.scrollTop;
                el.scrollTo(0, el.scrollHeight - 200);
                return {{scrollTop: prev, scrollHeight: el.scrollHeight}};
            }}""")
            
            if prev is None:
                print(f"   Scroll {i+1}: ❌ Container not found with selector '{container_selector}'!")
                break
            
            print(f"   Scroll {i+1}: scrollTop was {prev['scrollTop']}, scrollHeight was {prev['scrollHeight']}", end="", flush=True)
            
            # Wait for new content
            loaded = False
            for attempt in range(8):
                time.sleep(1)
                new = page.evaluate(f"""() => {{
                    const el = document.querySelector('{container_selector}');
                    return el ? el.scrollHeight : 0;
                }}""")
                if new > prev['scrollHeight']:
                    loaded = True
                    posts = count_posts(page)
                    print(f" → ✅ NEW! scrollHeight: {new}, posts: {posts}")
                    break
            
            if not loaded:
                posts = count_posts(page)
                cur = page.evaluate(f"""() => {{
                    const el = document.querySelector('{container_selector}');
                    return el ? {{scrollTop: el.scrollTop, scrollHeight: el.scrollHeight}} : null;
                }}""")
                print(f" → ⚠️ No new content. scrollTop: {cur['scrollTop'] if cur else '?'}, posts: {posts}")
            
            if i % 5 == 4:
                page.screenshot(path=f"test_feed_v2_scroll_{i+1}.png")
                input(f"\n   Paused after {i+1} scrolls. Press ENTER...\n")
        
        # --- STEP 4: Final results ---
        print("\n" + "=" * 60)
        final_posts = count_posts(page)
        print(f"📊 FINAL: {final_posts} posts in DOM")
        print(f"   Container selector: '{container_selector}'")
        
        page.screenshot(path="test_feed_v2_final.png")
        with open("test_feed_v2_final.html", "w") as f:
            f.write(page.content())
        print(f"   � test_feed_v2_final.png")
        
        input("\n🏁 Press ENTER to close browser...\n")
        browser.close()

if __name__ == "__main__":
    main()
