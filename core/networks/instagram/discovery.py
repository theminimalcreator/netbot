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

from core.logger import NetBotLoggerAdapter
logger = NetBotLoggerAdapter(logging.getLogger(__name__), {'network': 'Instagram'})


class InstagramDiscovery(DiscoveryStrategy):
    def __init__(self, client: InstagramClient):
        self.client = client
        self.vip_list = settings.load_vip_list("instagram")
        self.hashtags = settings.load_hashtags("instagram")

    def find_candidates(self, limit: int = 5) -> List[SocialPost]:
        """
        Returns a list of candidate posts to try interacting with.
        Tries multiple sources and falls back between VIP and Hashtag.
        """
        # Routing Logic: 70% VIP first, 30% Hashtag first
        use_vip_first = True
        if self.vip_list and self.hashtags:
            use_vip_first = random.random() < 0.7
        elif self.hashtags:
            use_vip_first = False
        elif not self.vip_list:
            logger.warning("No VIPs and No Hashtags defined!")
            return []

        # Try primary strategy, then fallback
        strategies = []
        if use_vip_first:
            strategies = [("VIP", self._fetch_from_vip), ("Hashtag", self._fetch_from_discovery)]
        else:
            strategies = [("Hashtag", self._fetch_from_discovery), ("VIP", self._fetch_from_vip)]

        for strategy_name, fetch_fn in strategies:
            candidates = fetch_fn(amount=limit)
            valid = [p for p in candidates if self.validate_candidate(p)]
            if valid:
                return valid
            logger.info(f"[Instagram] {strategy_name} returned no valid candidates, trying next...")

        return []

    def _fetch_from_vip(self, amount: int) -> List[SocialPost]:
        """Try up to 3 random VIPs and return first non-empty result."""
        if not self.vip_list:
            return []
        attempts = min(3, len(self.vip_list))
        tried = random.sample(self.vip_list, attempts)
        for target_user in tried:
            logger.info(f"Discovery: Checking VIP @{target_user}", stage='A')
            posts = self.client.get_user_latest_posts(target_user, limit=amount)
            if posts:
                return posts
        return []

    def _fetch_from_discovery(self, amount: int) -> List[SocialPost]:
        """Try up to 3 random hashtags and return first non-empty result."""
        if not self.hashtags:
            return []
        attempts = min(3, len(self.hashtags))
        tried = random.sample(self.hashtags, attempts)
        for target_tag in tried:
            logger.info(f"Discovery: Checking Hashtag #{target_tag}", stage='A')
            posts = self.client.search_posts(target_tag, limit=amount)
            if posts:
                random.shuffle(posts)
                return posts
        return []

    def validate_candidate(self, post: SocialPost) -> bool:
        """Filters out posts that are already interacted or owned by us."""
        if not post.id:
            return False
            
        # Check DB first (TODO: Update DB to support platform check)
        # For now, we assume global ID uniqueness or collision risk is low enough for MVP refactor
        if db.check_if_interacted(post.id, post.platform.value):
            logger.warning(f"Skipping {post.id}: Already interacted.", stage='B')
            return False

        # Check if already discovered/processed (seen, rejected, error)
        try:
            res = db.client.table("discovered_posts").select("status").eq("external_id", post.id).eq("platform", post.platform.value).execute()
            if res.data:
                status = res.data[0]['status']
                # If it was rejected or error, maybe we skip? Or retry?
                # If it was 'seen' but not interacted, it means it's pending or was skipped for other reasons
                if status in ['rejected', 'error', 'interacted']:
                    logger.warning(f"Skipping {post.id}: Previously {status}.", stage='B')
                    return False
        except Exception as e:
            logger.error(f"Error checking discovery status: {e}")

        # Ignore if it's our own post
        if post.author.username == settings.IG_USERNAME:
            return False
        
        # Ignore if no caption AND no image (agent can't do much)
        if not post.content and not post.media_urls:
            logger.warning(f"Skipping {post.id}: No caption/image context.", stage='B')
            return False
            
        return True

# Singleton removed — clients are now created per cycle in main.py
