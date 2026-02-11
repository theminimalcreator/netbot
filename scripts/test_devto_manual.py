import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from core.networks.devto.client import DevToClient
from core.networks.devto.discovery import DevToDiscovery
from core.models import SocialPost

def test_devto_integration():
    print("🚀 Check Settings...")
    if not settings.DEVTO_API_KEY:
        print("❌ DEVTO_API_KEY is missing in settings/env.")
        return

    print("🔌 Initializing Client...")
    client = DevToClient()
    if not client.login():
        print("❌ Login failed.")
        return
    print("✅ Login successful.")

    print("🕵️ Initializing Discovery...")
    discovery = DevToDiscovery(client)
    
    print("🔍 Finding candidates...")
    candidates = discovery.find_candidates(limit=2)
    
    if not candidates:
        print("⚠️ No candidates found. Check tags/vips.")
        return

    print(f"✅ Found {len(candidates)} candidates.")
    for i, post in enumerate(candidates):
        print(f"\n--- Post {i+1} ---")
        print(f"ID: {post.id}")
        print(f"Author: {post.author.username}")
        print(f"Title: {post.content.split('  ')[0] if post.content else 'No Content'}...")
        print(f"URL: {post.url}")
        
        # Verify Context fetching
        if post.comments:
            print(f"✅ Context: Found {len(post.comments)} recent comments.")
            print(f"   Sample: {post.comments[0].text[:50]}...")
        else:
            print("⚠️ No comments found for context (might be a new post).")

    print("\n✅ Verification Complete.")

if __name__ == "__main__":
    test_devto_integration()
