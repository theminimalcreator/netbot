import logging
from datetime import datetime
from supabase import create_client, Client
from config.settings import settings

logger = logging.getLogger(__name__)


class Database:
    """
    Supabase database wrapper for interactions, stats, and logging.
    """
    
    def __init__(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    def log_interaction(self, post_id: str, username: str, comment_text: str, metadata: dict = None):
        """Records a successful interaction."""
        data = {
            "post_id": post_id,
            "username": username,
            "comment_text": comment_text,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat()
        }
        try:
            self.client.table("interactions").insert(data).execute()
            self.increment_daily_count()
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
            self.log_app_event("ERROR", "database", f"Failed to log interaction: {e}")

    def increment_daily_count(self):
        """Updates the daily_stats table."""
        today = datetime.today().date().isoformat()
        try:
            res = self.client.table("daily_stats").select("*").eq("date", today).execute()
            if not res.data:
                self.client.table("daily_stats").insert({
                    "date": today,
                    "interaction_count": 1
                }).execute()
            else:
                current_count = res.data[0]["interaction_count"]
                self.client.table("daily_stats").update({
                    "interaction_count": current_count + 1,
                    "last_updated": datetime.now().isoformat()
                }).eq("date", today).execute()
        except Exception as e:
            logger.error(f"Error updating daily stats: {e}")

    def get_daily_count(self) -> int:
        """Returns the number of interactions made today."""
        today = datetime.today().date().isoformat()
        try:
            res = self.client.table("daily_stats").select("interaction_count").eq("date", today).execute()
            if res.data:
                return res.data[0]["interaction_count"]
            return 0
        except Exception as e:
            logger.error(f"Error fetching daily count: {e}")
            return 0

    def check_if_interacted(self, post_id: str) -> bool:
        """Checks if we already interacted with this specific post (deduplication)."""
        try:
            res = self.client.table("interactions").select("id").eq("post_id", post_id).execute()
            return len(res.data) > 0
        except Exception as e:
            logger.error(f"Error checking interaction: {e}")
            return False

    def log_app_event(self, level: str, module: str, message: str, details: dict = None):
        """Logs application events (INFO, ERROR, WARNING)."""
        try:
            data = {
                "level": level,
                "module": module,
                "message": message,
                "details": details or {}
            }
            self.client.table("logs").insert(data).execute()
        except Exception as e:
            # If logging fails, just print to console to avoid infinite loops
            logger.critical(f"Failed to send log to Supabase: {e}")


db = Database()
