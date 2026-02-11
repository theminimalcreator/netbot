import random
import logging
from typing import List
from config.settings import settings
from core.database import db
from core.networks.devto.client import DevToClient
from core.interfaces import DiscoveryStrategy
from core.models import SocialPost, SocialPlatform

logger = logging.getLogger(__name__)

class DevToDiscovery(DiscoveryStrategy):
    def __init__(self, client: DevToClient):
        self.client = client
        self.vip_list = settings.load_vip_list("devto")
        self.hashtags = settings.load_hashtags("devto")

    def find_candidates(self, limit: int = 5) -> List[SocialPost]:
        """
        Returns a list of candidate posts to interact with.
        Mixes VIPs and Hashtags.
        """
        candidates = []
        
        # 1. VIP Strategy (50% chance)
        if self.vip_list and random.random() < 0.5:
            username = random.choice(self.vip_list)
            logger.info(f"[DevTo] Discovery: Checking VIP @{username}")
            vip_posts = self.client.get_user_latest_posts(username, limit=limit)
            candidates.extend(vip_posts)
            
        # 2. Tag Strategy (always try if VIP yielded nothing or didn't run)
        if not candidates and self.hashtags:
            tag = random.choice(self.hashtags)
            logger.info(f"[DevTo] Discovery: Checking Tag #{tag}")
            tag_posts = self.client.search_posts(tag, limit=limit)
            candidates.extend(tag_posts)
            
        # Validate & Fetch
        valid_candidates = []
        for post in candidates:
            if limit and len(valid_candidates) >= limit:
                break
                
            if self.validate_candidate(post):
                # Fetch full details (lazy fetch)
                full_post = self.client.get_post_details(post.id)
                if full_post:
                    valid_candidates.append(full_post)
        
        return valid_candidates

    def validate_candidate(self, post: SocialPost) -> bool:
        """Filters out invalid posts."""
        if not post.id:
            return False
            
        # Check DB for previous interaction
        if db.check_if_interacted(post.id, SocialPlatform.DEVTO.value):
            logger.debug(f"[DevTo] Skipping {post.id}: Already interacted.")
            return False

        # Ignore if it's our own post (if we had a username check)
        # Assuming we don't post much yet.
        
        return True
