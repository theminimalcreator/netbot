"""
Twitter Discovery Engine
"""
import random
import logging
from typing import List
from config.settings import settings
from core.database import db
from core.networks.twitter.client import TwitterClient
from core.interfaces import DiscoveryStrategy
from core.models import SocialPost

logger = logging.getLogger(__name__)

# We need a client instance for discovery to work (fetching posts)
# Ideally this should be injected or singleton
# For now, we'll instantiate one or expect it to be passed, but the pattern in IG was global client.
# Let's assume we use the client from main.py or we create a new one for discovery if needed, 
# but sharing session is better. 
# Refactor: In main.py we pass client to find_candidates? Or we import a singleton?
# IG uses `from core.networks.instagram.client import client`. 
# Let's create a singleton instance in client.py similar to IG.

# Temporary local client instantiation if not imported, 
# but better to follow IG pattern:
# from core.networks.twitter.client import client as twitter_client

class TwitterDiscovery(DiscoveryStrategy):
    def __init__(self, client: TwitterClient):
        self.client = client
        self.vip_list = settings.load_vip_list("twitter")
        self.hashtags = settings.load_hashtags("twitter")

    def find_candidates(self, limit: int = 5) -> List[SocialPost]:
        candidates = []
        
        use_vip = True
        if self.vip_list and self.hashtags:
            use_vip = random.random() < 0.7
        elif self.hashtags:
            use_vip = False
        elif not self.vip_list:
            logger.warning("Twitter: No VIPs and No Hashtags defined!")
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
        logger.info(f"Twitter Discovery: Checking VIP @{target_user}")
        return self.client.get_user_latest_posts(target_user, limit=amount)

    def _fetch_from_discovery(self, amount: int) -> List[SocialPost]:
        if not self.hashtags: return []
        target_tag = random.choice(self.hashtags)
        logger.info(f"Twitter Discovery: Checking Hashtag #{target_tag}")
        posts = self.client.search_posts(target_tag, limit=amount)
        random.shuffle(posts)
        return posts

    def validate_candidate(self, post: SocialPost) -> bool:
        if not post.id: return False
        if db.check_if_interacted(post.id, post.platform.value):
            logger.debug(f"Skipping {post.id}: Already interacted.")
            return False
        return True
