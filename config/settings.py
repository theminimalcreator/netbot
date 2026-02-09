import os
import json
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"

class Settings:
    BASE_DIR = Path(__file__).resolve().parent.parent
    CONFIG_DIR = BASE_DIR / "config"

    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    IG_USERNAME = os.getenv("IG_USERNAME")
    IG_PASSWORD = os.getenv("IG_PASSWORD")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    # Postgres Connection for Agno KnowledgeBase (SQLAlchemy)
    PG_DATABASE_URL = os.getenv("PG_DATABASE_URL")

    # Bot Limits
    daily_interaction_limit = int(os.getenv("DAILY_INTERACTION_LIMIT", "2"))
    min_sleep_interval = int(os.getenv("MIN_SLEEP_INTERVAL", "600")) # 10 minutes
    max_sleep_interval = int(os.getenv("MAX_SLEEP_INTERVAL", "3000")) # 50 minutes
    dry_run = os.getenv("DRY_RUN", "True").lower() == "true"
    
    # Proxy (optional, helps avoid IP bans)
    PROXY_URL = os.getenv("PROXY_URL", None)
    
    # Debug mode - show browser window
    DEBUG_HEADLESS = os.getenv("DEBUG_HEADLESS", "True").lower() == "true"

    # Files
    VIP_LIST_PATH = CONFIG_DIR / "vip_list.json"
    HASHTAGS_PATH = CONFIG_DIR / "hashtags.json"
    PROMPTS_PATH = CONFIG_DIR / "prompts.yaml"

    # Device Emulation (Samsung Galaxy Z Fold 5)
    # Using high-end Android settings
    DEVICE_SETTINGS = {
        "app_version": "315.0.0.35.109",
        "android_version": 34, # Android 14
        "android_release": "14.0",
        "dpi": "480dpi",
        "resolution": "1812x2176",
        "manufacturer": "Samsung",
        "device": "SM-F946B", # Galaxy Z Fold 5
        "model": "Galaxy Z Fold 5",
        "cpu": "qcom",
        "version_code": "564456345"
    }

    @classmethod
    def load_vip_list(cls):
        if cls.VIP_LIST_PATH.exists():
            with open(cls.VIP_LIST_PATH, "r") as f:
                return json.load(f)
        return []

    @classmethod
    def load_hashtags(cls):
        if cls.HASHTAGS_PATH.exists():
            with open(cls.HASHTAGS_PATH, "r") as f:
                return json.load(f)
        return []

    @classmethod
    def load_prompts(cls):
        if cls.PROMPTS_PATH.exists():
            with open(cls.PROMPTS_PATH, "r") as f:
                return yaml.safe_load(f)
        return {}

settings = Settings()
