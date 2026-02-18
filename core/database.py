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

    def log_interaction(self, post_id: str, username: str, comment_text: str, platform: str, metadata: dict = None):
        """Records a successful interaction."""
        data = {
            "post_id": post_id,
            "username": username,
            "comment_text": comment_text,
            "platform": platform,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat()
        }
        try:
            self.client.table("interactions").insert(data).execute()
            self.increment_daily_count(platform)
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
            self.log_app_event("ERROR", "database", f"Failed to log interaction: {e}")

    def increment_daily_count(self, platform: str):
        """Updates the daily_stats table for the specific platform atomically."""
        try:
            # Call the atomic RPC function instead of read-then-write
            self.client.rpc("increment_daily_stats", {"p_platform": platform}).execute()
        except Exception as e:
            logger.error(f"Error updating daily stats: {e}")

    def get_daily_count(self, platform: str) -> int:
        """Returns the number of interactions made today for the specific platform."""
        today = datetime.today().date().isoformat()
        try:
            res = self.client.table("daily_stats").select("interaction_count").eq("date", today).eq("platform", platform).execute()
            if res.data:
                return res.data[0]["interaction_count"]
            return 0
        except Exception as e:
            logger.error(f"Error fetching daily count: {e}")
            return 0

    def check_if_interacted(self, post_id: str, platform: str) -> bool:
        """Checks if we already interacted with this specific post (deduplication)."""
        try:
            res = self.client.table("interactions").select("id").eq("post_id", post_id).eq("platform", platform).execute()
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

    def log_discovery(self, post_id: str, platform: str, source: str, metrics: dict) -> str:
        """
        Logs a discovered post.
        Returns the ID if successful, or None if it already exists/fails.
        """
        try:
            data = {
                "external_id": post_id,
                "platform": platform,
                "hashtag_source": source,
                "metrics": metrics,
                "status": "seen",
                "created_at": datetime.now().isoformat()
            }
            # Use upsert to handle potential race conditions or re-discovery
            # on_conflict="external_id, platform" is implied by the unique constraint
            res = self.client.table("discovered_posts").upsert(data, on_conflict="external_id, platform").execute()
            
            if res.data:
                return res.data[0]["id"]
            return None
        except Exception as e:
            logger.error(f"Error logging discovery for {platform}/{post_id}: {e}")
            return None

    def update_discovery_status(self, external_id: str, platform: str, status: str, reasoning: str = None):
        """Updates the status and reasoning of a discovered post by external_id and platform."""
        try:
            data = {"status": status, "updated_at": datetime.now().isoformat()}
            if reasoning:
                data["ai_reasoning"] = reasoning
            
            self.client.table("discovered_posts").update(data).eq("external_id", external_id).eq("platform", platform).execute()
        except Exception as e:
            logger.error(f"Error updating discovery status {external_id}: {e}")

    def log_llm_interaction(self, 
                            provider: str, 
                            model: str, 
                            user_prompt: str, 
                            response: str, 
                            system_prompt: str = None, 
                            parameters: dict = None, 
                            metrics: dict = None, 
                            metadata: dict = None) -> str:
        """
        Logs an LLM interaction to the llm_logs table.
        """
        try:
            data = {
                "provider": provider,
                "model": model,
                "user_prompt": user_prompt,
                "response": response,
                "system_prompt": system_prompt,
                "parameters": parameters or {},
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            if metrics:
                data["input_tokens"] = metrics.get('input_tokens')
                data["output_tokens"] = metrics.get('output_tokens')
                data["total_cost"] = metrics.get('total_cost')

            res = self.client.table("llm_logs").insert(data).execute()
            if res.data:
                return res.data[0]["id"]
            return None

        except Exception as e:
            logger.error(f"Error logging LLM interaction: {e}")
            self.log_app_event("ERROR", "llm_logger", f"Failed to log LLM interaction: {e}")
            return None

    def get_count(self, table: str, filters: dict) -> int:
        """
        Generic count with improved filtering for dashboards.
        Supports 'GTE:' prefix for date comparisons.
        """
        try:
            query = self.client.table(table).select("id", count="exact")
            
            for key, value in filters.items():
                if isinstance(value, list):
                    # In query
                    query = query.in_(key, value)
                elif isinstance(value, str) and value.startswith("GTE:"):
                    # Greater than or equal to date
                    clean_val = value.replace("GTE:", "")
                    query = query.gte(key, clean_val)
                else:
                    # Generic equals
                    query = query.eq(key, value)
            
            res = query.execute()
            return res.count if res.count is not None else 0
        except Exception as e:
            logger.error(f"Error counting {table}: {e}")
            return 0

    def get_recent_interactions(self, limit: int = 5) -> list:
        """
        Fetches the most recent interactions for the dashboard.
        """
        try:
            res = self.client.table("interactions").select("*").order("created_at", desc=True).limit(limit).execute()
            return res.data
        except Exception as e:
            logger.error(f"Error fetching recent interactions: {e}")
            return []

    def get_interactions_since(self, timestamp: datetime) -> list:
        """
        Fetches all interactions created after the given timestamp.
        """
        try:
            res = self.client.table("interactions").select("*").gte("created_at", timestamp.isoformat()).order("created_at", desc=True).execute()
            return res.data
        except Exception as e:
            logger.error(f"Error fetching interactions since {timestamp}: {e}")
            return []

    def get_token_usage_since(self, timestamp: datetime) -> dict:
        """
        Aggregates token usage and cost since the given timestamp.
        Returns {'input_tokens': int, 'output_tokens': int, 'total_cost': float}
        """
        try:
            # Supabase/Postgrest doesn't support sum() aggregation directly in simple client easily without RPC
            # But the client wrapper might not expose it. 
            # We can fetch selected columns and sum in python if the volume isn't huge (cycle logs usually small < 50 items).
            res = self.client.table("llm_logs") \
                .select("input_tokens,output_tokens,total_cost") \
                .gte("created_at", timestamp.isoformat()) \
                .execute()
            
            data = res.data or []
            return {
                "input_tokens": sum(item.get('input_tokens') or 0 for item in data),
                "output_tokens": sum(item.get('output_tokens') or 0 for item in data),
                "total_cost": sum(item.get('total_cost') or 0.0 for item in data)
            }
        except Exception as e:
            logger.error(f"Error fetching token usage: {e}")
            return {"input_tokens": 0, "output_tokens": 0, "total_cost": 0.0}

db = Database()

