"""
LinkedIn Discovery Strategy
Feed First -> Topic Search Fallback
"""
import random
import logging
from typing import List

from config.settings import settings
from core.database import db
from core.networks.linkedin.client import LinkedInClient
from core.interfaces import DiscoveryStrategy
from core.models import SocialPost, SocialPlatform
from core.logger import NetBotLoggerAdapter

logger = NetBotLoggerAdapter(logging.getLogger(__name__), {'network': 'LinkedIn'})

class LinkedInDiscovery(DiscoveryStrategy):
    def __init__(self, client: LinkedInClient):
        self.client = client
        # Load topics using the hashtags loader (same JSON structure)
        self.topics = settings.load_hashtags("linkedin")

    def find_candidates(self, limit: int = 5) -> List[SocialPost]:
        """
        Feed-first discovery:
        1. Browse home feed for relevant posts
        2. Fallback: search by random topic
        """
        strategies = [
            ("Feed", self._fetch_from_feed),
            ("Topic Search", self._fetch_from_topics),
        ]

        for name, fetch_fn in strategies:
            logger.info(f"Discovery: Trying {name}...", stage='A')
            try:
                candidates = fetch_fn(limit=limit)
                valid = [p for p in candidates if self.validate_candidate(p)]
                
                if valid:
                    logger.info(f"Discovery: Found {len(valid)} valid candidates from {name}.", stage='A')
                    return valid
                
                logger.info(f"{name} yielded no valid candidates.")
            except Exception as e:
                 logger.error(f"Error in strategy {name}: {e}")

        return []

    def _fetch_from_feed(self, limit: int) -> List[SocialPost]:
        """Scrape posts from the home feed."""
        return self.client.get_feed_posts(limit=limit)

    def _fetch_from_topics(self, limit: int) -> List[SocialPost]:
        """Search for posts by random topic. Retry up to 3 topics."""
        if not self.topics:
            logger.warning("No topics configured for LinkedIn search.")
            return []
            
        attempts = min(3, len(self.topics))
        tried = random.sample(self.topics, attempts)
        
        for topic in tried:
            logger.info(f"Discovery: Searching topic '{topic}'", stage='A')
            posts = self.client.search_posts(topic, limit=limit)
            if posts:
                random.shuffle(posts)
                return posts
        return []

    def validate_candidate(self, post: SocialPost) -> bool:
        """Standard validation: dedup + content check."""
        if not post.id:
            return False

        # Log discovery
        metrics = getattr(post, 'metrics', {})
        # Ensure URL is saved for dashboard
        if getattr(post, 'url', None):
            metrics['url'] = post.url
            
        try:
            db.log_discovery(post.id, post.platform.value, "discovery", metrics)
        except Exception as e:
            logger.warning(f"Failed to log discovery for {post.id}: {e}")

        # Dedup: check interaction history
        if db.check_if_interacted(post.id, SocialPlatform.LINKEDIN.value):
            logger.warning(f"Skipping {post.id}: Already interacted.", stage='B')
            try:
                db.update_discovery_status(
                    post.id, post.platform.value, "skipped", "Already interacted"
                )
            except: pass
            return False
            
        # Check if already in process via 'discovered_posts' check done inside main loop usually, 
        # but db.check_if_interacted checks the 'interactions' table.
        # We might also want to check if we previously rejected it.
        # (Simplified for now to rely on interaction check)

        # Must have content for the agent to analyze (LinkedIn often has image-only ads)
        if not post.content or len(post.content) < 10:
            logger.warning(f"Skipping {post.id}: Content too short/empty.", stage='B')
             # Log skip
            try:
                db.update_discovery_status(post.id, post.platform.value, "skipped", "Low content")
            except: pass
            return False
            
        # Check for Promoted/Ads (heuristic in content or specific field)
        if "Promoted" in post.content: # Basic check
             return False

        return True
