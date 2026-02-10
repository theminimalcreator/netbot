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
        candidates = []
        
        use_vip = True
        if self.vip_list and self.hashtags:
            use_vip = random.random() < 0.7
        elif self.hashtags:
            use_vip = False
        elif not self.vip_list:
            logger.warning("Threads: No VIPs and No Hashtags defined!")
            return []

        if use_vip:
            candidates = self._fetch_from_vip(amount=limit)
        else:
            candidates = self._fetch_from_discovery(amount=limit)
        
        valid_candidates = [
            post for post in candidates 
            if self.validate_candidate(post)
        ]
        return valid_candidates

    def _fetch_from_vip(self, amount: int) -> List[SocialPost]:
        if not self.vip_list: return []
        target_user = random.choice(self.vip_list)
        logger.info(f"Threads Discovery: Checking VIP @{target_user}")
        return self.client.get_user_latest_posts(target_user, limit=amount)

    def _fetch_from_discovery(self, amount: int) -> List[SocialPost]:
        if not self.hashtags: return []
        target_tag = random.choice(self.hashtags)
        logger.info(f"Threads Discovery: Checking Hashtag #{target_tag}")
        posts = self.client.search_posts(target_tag, limit=amount)
        random.shuffle(posts)
        return posts

    def validate_candidate(self, post: SocialPost) -> bool:
        if not post.id: return False
        if db.check_if_interacted(post.id, post.platform.value):
            logger.debug(f"Skipping {post.id}: Already interacted.")
            return False
        return True
