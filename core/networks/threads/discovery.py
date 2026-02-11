"""
Threads Discovery Engine
"""
import random
import logging
from typing import List
from config.settings import settings
from core.database import db
from core.networks.threads.client import ThreadsClient
from core.interfaces import DiscoveryStrategy
from core.models import SocialPost

logger = logging.getLogger(__name__)

class ThreadsDiscovery(DiscoveryStrategy):
    def __init__(self, client: ThreadsClient):
        self.client = client
        self.vip_list = settings.load_vip_list("threads")
        self.hashtags = settings.load_hashtags("threads")

    def find_candidates(self, limit: int = 5) -> List[SocialPost]:
        """Tries multiple sources and falls back between VIP and Hashtag."""
        use_vip_first = True
        if self.vip_list and self.hashtags:
            use_vip_first = random.random() < 0.7
        elif self.hashtags:
            use_vip_first = False
        elif not self.vip_list:
            logger.warning("Threads: No VIPs and No Hashtags defined!")
            return []

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
            logger.info(f"[Threads] {strategy_name} returned no valid candidates, trying next...")

        return []

    def _fetch_from_vip(self, amount: int) -> List[SocialPost]:
        """Try up to 3 random VIPs and return first non-empty result."""
        if not self.vip_list: return []
        attempts = min(3, len(self.vip_list))
        tried = random.sample(self.vip_list, attempts)
        for target_user in tried:
            logger.info(f"Threads Discovery: Checking VIP @{target_user}")
            posts = self.client.get_user_latest_posts(target_user, limit=amount)
            if posts:
                return posts
        return []

    def _fetch_from_discovery(self, amount: int) -> List[SocialPost]:
        """Try up to 3 random hashtags and return first non-empty result."""
        if not self.hashtags: return []
        attempts = min(3, len(self.hashtags))
        tried = random.sample(self.hashtags, attempts)
        for target_tag in tried:
            logger.info(f"Threads Discovery: Checking Hashtag #{target_tag}")
            posts = self.client.search_posts(target_tag, limit=amount)
            if posts:
                random.shuffle(posts)
                return posts
        return []

    def validate_candidate(self, post: SocialPost) -> bool:
        if not post.id: return False
        if db.check_if_interacted(post.id, post.platform.value):
            logger.debug(f"Skipping {post.id}: Already interacted.")
            return False
        return True
