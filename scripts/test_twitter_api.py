"""
Test Script for Twitter API Integration
"""
import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.networks.twitter.client import TwitterClient
from config.settings import settings

def test_twitter_api():
    print("🐦 Testing Twitter API Integration")
    print("=" * 50)

    # Check credentials
    print(f"API Key: {'✅ Present' if settings.TWITTER_API_KEY else '❌ Missing'}")
    print(f"API Secret: {'✅ Present' if settings.TWITTER_API_SECRET else '❌ Missing'}")
    print(f"Access Token: {'✅ Present' if settings.TWITTER_ACCESS_TOKEN else '❌ Missing'}")
    print(f"Access Secret: {'✅ Present' if settings.TWITTER_ACCESS_TOKEN_SECRET else '❌ Missing'}")
    
    if not (settings.TWITTER_API_KEY and settings.TWITTER_API_SECRET and 
            settings.TWITTER_ACCESS_TOKEN and settings.TWITTER_ACCESS_TOKEN_SECRET):
        print("\n❌ Missing Twitter API credentials in .env file.")
        print("Please add TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET to your .env file.")
        return False

    client = TwitterClient()
    if not client.api_client:
        print("\n❌ Failed to initialize Twitter API Client.")
        return False
    
    print("\n✅ Twitter API Client initialized.")
    
    # 1. Test Posting
    test_message = f"Test automated post from NetBot API integration [Timestamp: {int(time.time())}]"
    print(f"\n1. Attempting to post: '{test_message}'...")
    
    # We use internal method or direct API call to verify?
    # Let's use the client's method to test the full flow
    result = client.post_content(test_message)
    
    if result == "success":
        print("✅ Post successful!")
    else:
        print("❌ Post failed.")
        return False
        
    # Since we don't easily get the ID back from post_content (it returns "success" string), 
    # capturing the ID in the client for testing would have been better. 
    # But let's check the logs or just try to fetch user's timeline to find it?
    # API read is usually limited on free tier, but let's try reading own timeline if possible?
    # Actually, tweepy client.create_tweet returns the response which has the ID.
    # We modified post_content to log the ID.

    # For verification script, let's use the API client directly to delete it if we can find it, 
    # OR inform user to check their profile.
    
    print("\n⚠️  Note: Verify the post appeared on your profile.")
    print("   Since `post_content` wraps the return value, we can't automatically get the ID to delete it in this script without modifying the method to return ID.")
    
    return True

if __name__ == "__main__":
    test_twitter_api()
