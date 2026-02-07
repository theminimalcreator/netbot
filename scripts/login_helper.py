import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagrapi.exceptions import ChallengeRequired, BadPassword, TwoFactorRequired
from core.instagram_client import client
from config.settings import settings

def interactive_login():
    print("🔐 Starting Interactive Login Helper...")
    print(f"User: {settings.IG_USERNAME}")
    
    try:
        # Try to login normally first
        if client.login():
            print("✅ Login Successful! Session saved.")
            return
            
    except BadPassword:
        print("❌ Wrong Password! Check .env")
        return
        
    except (ChallengeRequired, TwoFactorRequired) as e:
        print(f"\n⚠️  IG detected a challenge: {e}")
        
    # If we are here, we might need to handle the challenge manually on the client object
    # client.login() in our core catches the exception, so we might need to access the internal cl object directly
    # to handle the flow properly.
    
    cl = client.cl
    
    try:
         # Trigger login again on the raw client to catch the exception here
        cl.login(settings.IG_USERNAME, settings.IG_PASSWORD)
    except (ChallengeRequired, TwoFactorRequired) as e:
        # Resolve Challenge
        print("📲 Challenge Required. Attempting to resolve...")
        
        try:
            # Check if we can send a code
            # Note: The exact method depends on what IG returns. 
            # Often cl.challenge_resolve(cl.last_json) works.
            
            # 1. Ask for code method
            # In complex cases, we might need to choose SMS or Email. 
            # Instagrapi tries to automate this but sometimes needs help.
            
            code = input("⌨️  Enter the code sent to your SMS/Email/App: ")
            
            # Depending on the exception, we might need different methods
            if isinstance(e, TwoFactorRequired):
                cl.two_factor_login(code)
            else:
                cl.challenge_code_handler = lambda x, y: code
                cl.challenge_resolve(cl.last_json)
                
            print("✅ Challenge Solved! Saving session...")
            cl.dump_settings(client.session_path)
            print("🎉 Session saved to session.json")
            
        except Exception as e2:
            print(f"❌ Failed to resolve challenge: {e2}")
            
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    interactive_login()
