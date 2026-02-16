
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import db

def reset_linkedin():
    print("WARNING: This will delete ALL LinkedIn interaction history and discovery logs.")
    confirm = input("Are you sure? (yes/no): ")
    if confirm.lower() != "yes":
        print("Aborted.")
        return

    try:
        print("Deleting from 'interactions'...")
        db.client.table("interactions").delete().eq("platform", "linkedin").execute()
        
        print("Deleting from 'discovered_posts'...")
        db.client.table("discovered_posts").delete().eq("platform", "linkedin").execute()
        
        # Reset daily stats? Maybe not necessary, but good for testing limits
        print("Resetting daily stats for linkedin...")
        db.client.table("daily_stats").delete().eq("platform", "linkedin").execute()

        print("✅ LinkedIn history reset successfully!")
    except Exception as e:
        print(f"❌ Error resetting database: {e}")

if __name__ == "__main__":
    reset_linkedin()
