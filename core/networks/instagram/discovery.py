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
from core.networks.instagram.client import InstagramClient
from core.interfaces import DiscoveryStrategy
from core.models import SocialPost

logger = logging.getLogger(__name__)


class InstagramDiscovery(DiscoveryStrategy):
    def __init__(self, client: InstagramClient):
        self.client = client
        self.vip_list = settings.load_vip_list("instagram")
        self.hashtags = settings.load_hashtags("instagram")

    def find_candidates(self, limit: int = 5) -> List[SocialPost]:
        """
        Returns a list of candidate posts to try interacting with.
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
            post for post in candidates 
            if self.validate_candidate(post)
        ]
        
        return valid_candidates

    def _fetch_from_vip(self, amount: int) -> List[SocialPost]:
        """Pick a random VIP and get their latest posts."""
        target_user = random.choice(self.vip_list)
        logger.info(f"Discovery: Checking VIP @{target_user}")
        
        # Fetch more to allow for filtering
        return self.client.get_user_latest_posts(target_user, limit=amount)

    def _fetch_from_discovery(self, amount: int) -> List[SocialPost]:
        """Pick a random hashtag and get top posts."""
        target_tag = random.choice(self.hashtags)
        logger.info(f"Discovery: Checking Hashtag #{target_tag}")
        
        # Fetch more to allow for filtering
        # Note: client.search_posts wraps get_hashtag_top_medias
        posts = self.client.search_posts(target_tag, limit=amount)
        random.shuffle(posts)
        return posts

    def validate_candidate(self, post: SocialPost) -> bool:
        """Filters out posts that are already interacted or owned by us."""
        if not post.id:
            return False
            
        # Check DB first (TODO: Update DB to support platform check)
        # For now, we assume global ID uniqueness or collision risk is low enough for MVP refactor
        if db.check_if_interacted(post.id, post.platform.value):
            logger.debug(f"Skipping {post.id}: Already interacted.")
            return False

        # Ignore if it's our own post
        if post.author.username == settings.IG_USERNAME:
            return False
        
        # Ignore if no caption AND no image (agent can't do much)
        if not post.content and not post.media_urls:
            logger.debug(f"Skipping {post.id}: No caption/image context.")
            return False
            
        return True

# Singleton removed — clients are now created per cycle in main.py
