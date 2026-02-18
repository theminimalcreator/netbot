import requests
import logging
import os
from config.settings import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Sends notifications via Telegram Bot API.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
    """
    
    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not found. Notifications will be skipped.")

    def send_message(self, text: str, parse_mode: str = "HTML") -> str:
        """
        Sends a message to the configured chat.
        Returns the message_id if successful, None otherwise.
        """
        if not self.token or not self.chat_id:
            logger.info("Skipping Telegram notification (no credentials).")
            return None

        url = f"{self.BASE_URL}{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
        #    "parse_mode": parse_mode # Optional, disable if causing issues with raw text
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                logger.info("✅ Telegram notification sent.")
                return str(data["result"]["message_id"])
            else:
                logger.error(f"Telegram API error: {data}")
                return None
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return None
