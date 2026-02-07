"""
Discovery Engine

Selects candidate posts for interaction based on VIP list and hashtags.
Adapted for Playwright-based Instagram client with retry logic.
"""
import random
import logging
from typing import Optional, Dict, Any, List
from config.settings import settings
from core.database import db
from core.instagram_client import client

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    def __init__(self):
        self.vip_list = settings.load_vip_list()
        self.hashtags = settings.load_hashtags()

    def get_candidate_posts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Returns a list of candidate posts to try interacting with.
        This allows the main loop to retry if one post fails.
        """
        candidates = []
        
        # Routing Logic: 70% VIP, 30% Discovery
        use_vip = True
        if self.vip_list and self.hashtags:
            use_vip = random.random() < 0.7
        elif self.hashtags:
            use_vip = False
        elif not self.vip_list:
            logger.warning("No VIPs and No Hashtags defined!")
            return []

        if use_vip:
            candidates = self._fetch_from_vip(amount=limit)
        else:
            candidates = self._fetch_from_discovery(amount=limit)
        
        # Filter valid ones
        valid_candidates = [
            media for media in candidates 
            if self._is_valid_candidate(media)
        ]
        
        return valid_candidates

    def _fetch_from_vip(self, amount: int) -> List[Dict[str, Any]]:
        """Pick a random VIP and get their latest posts."""
        target_user = random.choice(self.vip_list)
        logger.info(f"Discovery: Checking VIP @{target_user}")
        
        # Fetch more to allow for filtering
        return client.get_user_latest_medias(target_user, amount=amount)

    def _fetch_from_discovery(self, amount: int) -> List[Dict[str, Any]]:
        """Pick a random hashtag and get top posts."""
        target_tag = random.choice(self.hashtags)
        logger.info(f"Discovery: Checking Hashtag #{target_tag}")
        
        # Fetch more to allow for filtering
        medias = client.get_hashtag_top_medias(target_tag, amount=amount)
        random.shuffle(medias)
        return medias

    def _is_valid_candidate(self, media: Dict[str, Any]) -> bool:
        """Filters out posts that are already interacted or owned by us."""
        media_id = media.get('media_id') or media.get('pk') or media.get('code')
        
        if not media_id:
            return False
            
        # Check DB first
        if db.check_if_interacted(media_id):
            logger.debug(f"Skipping {media_id}: Already interacted.")
            return False

        # Ignore if it's our own post
        if media.get('username') == settings.IG_USERNAME:
            return False
        
        # Ignore if no caption (agent can't do much)
        if not media.get('caption') and not media.get('image_url'):
            logger.debug(f"Skipping {media_id}: No caption/image context.")
            return False
            
        return True


discovery = DiscoveryEngine()
