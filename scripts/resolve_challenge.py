"""
Instagram Challenge Resolver
This script handles the challenge_required flow by:
1. Attempting login
2. Catching the challenge
3. Requesting verification code (SMS/Email)
4. Allowing user to input the code
5. Saving the session
"""
import sys
import os
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired, BadPassword
from config.settings import settings


def get_code_from_user(username, choice):
    """Called by instagrapi when it needs the verification code."""
    code = input(f"\n📲 Enter the verification code sent to your {choice}: ").strip()
    return code


def challenge_code_handler(username, choice):
    """Handler for challenge code - instagrapi will call this."""
    return get_code_from_user(username, choice)


def resolve_challenge():
    print("🔐 Instagram Challenge Resolver")
    print("=" * 50)
    print(f"Account: {settings.IG_USERNAME}")
    print("=" * 50)
    
    cl = Client()
    
    # Setup device settings
    cl.set_device(settings.DEVICE_SETTINGS)
    cl.set_locale("pt_BR")
    cl.set_country("BR")
    cl.set_timezone_offset(-3 * 3600)
    cl.delay_range = [3, 10]
    
    # Set the challenge code handler
    cl.challenge_code_handler = challenge_code_handler
    
    session_path = Path("session.json")
    
    # Delete old session if exists
    if session_path.exists():
        print("🗑️  Removing old session file...")
        session_path.unlink()
    
    try:
        print("\n🔄 Attempting login...")
        logged_in = cl.login(
            settings.IG_USERNAME, 
            settings.IG_PASSWORD,
            relogin=True
        )
        
        if logged_in:
            print("\n✅ Login Successful!")
            cl.dump_settings(session_path)
            print(f"💾 Session saved to: {session_path.absolute()}")
            print("\n🎉 You can now run: python3 main.py")
            return True
            
    except BadPassword:
        print("\n❌ Wrong password! Check your .env file.")
        return False
        
    except TwoFactorRequired:
        print("\n📱 Two-Factor Authentication required!")
        code = input("Enter your 2FA code: ").strip()
        try:
            cl.two_factor_login(code)
            print("\n✅ 2FA Login Successful!")
            cl.dump_settings(session_path)
            print(f"💾 Session saved to: {session_path.absolute()}")
            return True
        except Exception as e:
            print(f"\n❌ 2FA failed: {e}")
            return False
            
    except ChallengeRequired as e:
        print(f"\n⚠️  Challenge Required: {e}")
        print("\nThe challenge handler should have been called automatically.")
        print("If you didn't see a prompt for the code, the challenge type may not be supported.")
        
        # Try to get challenge info
        try:
            challenge_url = cl.last_json.get("challenge", {}).get("url")
            if challenge_url:
                print(f"\n🔗 Challenge URL: {challenge_url}")
                print("\nTry opening this URL in your browser while logged in to Instagram.")
        except:
            pass
            
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    resolve_challenge()
