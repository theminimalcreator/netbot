"""
Test Script: Twitter Flow
Runs the Twitter Client in headful mode to verify navigation and discovery.
"""
import sys
import os
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.networks.twitter.client import TwitterClient
from core.networks.twitter.discovery import TwitterDiscovery
from config.settings import settings

# Force Headful for this test
settings.DEBUG_HEADLESS = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TwitterTest")

def main():
    print("🐦 Starting Twitter Flow Test...")
    
    # 1. Initialize Client
    client = TwitterClient()
    
    # 2. Login
    if not client.login():
        print("❌ Login failed. Have you run scripts/login_twitter.py?")
        return

    # 3. Initialize Discovery with this client
    discovery = TwitterDiscovery(client)
    
    # 4. Search Candidates (This tests VIP/Hashtag lists)
    print("\n🔍 Searching for candidates...")
    candidates = discovery.find_candidates(limit=3)
    
    print(f"\n✅ Found {len(candidates)} candidates:")
    for i, post in enumerate(candidates):
        print(f"   {i+1}. @{post.author.username}: {post.content[:50]}... [{post.url}]")
    
    # 5. Visit a post (Simulation of interaction)
    if candidates:
        target = candidates[0]
        print(f"\n👀 Visiting first candidate: {target.id}")
        details = client.get_post_details(target.id)
        if details:
             print(f"   Accessed Content: {details.content[:100]}...")
        else:
             print("   ❌ Failed to get details.")

    print("\n🎉 Test Finished. Closing in 5 seconds...")
    time.sleep(5)
    client.stop()

if __name__ == "__main__":
    main()
