from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from core.models import SocialPost, SocialAuthor, ActionDecision, SocialPlatform, SocialProfile

class SocialNetworkClient(ABC):
    """
    Abstract interface that all network plugins (Instagram, Threads, etc.) must implement.
    """
    
    @property
    @abstractmethod
    def platform(self) -> SocialPlatform:
        pass

    @abstractmethod
    def login(self) -> bool:
        """Authenticates with the network."""
        pass

    @abstractmethod
    def stop(self):
        """Clean up resources (close browser, connection)."""
        pass
    
    @abstractmethod
    def get_post_details(self, post_id: str) -> Optional[SocialPost]:
        """Fetches full details of a specific post."""
        pass

    @abstractmethod
    def like_post(self, post: SocialPost) -> bool:
        """Likes a post."""
        pass

    @abstractmethod
    def post_comment(self, post: SocialPost, text: str) -> bool:
        """Posts a comment on a post."""
        pass

    # Optional methods (can raise NotImplementedError or return None if not supported)
    def search_posts(self, query: str, limit: int = 10) -> List[SocialPost]:
        return []
        
    def get_user_latest_posts(self, username: str, limit: int = 5) -> List[SocialPost]:
        return []

    def get_profile_data(self, username: str) -> Optional['SocialProfile']:
        """Fetches profile information (bio, stats) and recent posts."""
        return None

class DiscoveryStrategy(ABC):
    """
    Abstract interface for finding content to interact with.
    """
    
    @abstractmethod
    def find_candidates(self, limit: int = 5) -> List[SocialPost]:
        """Returns a list of candidate posts to analyze."""
        pass

    @abstractmethod
    def validate_candidate(self, post: SocialPost) -> bool:
        """Filters out posts (e.g., already interacted, own posts, too old)."""
        pass
