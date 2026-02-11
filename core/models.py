from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class SocialPlatform(str, Enum):
    INSTAGRAM = "instagram"
    THREADS = "threads"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    BLUESKY = "bluesky"
    DEVTO = "devto"

class SocialAuthor(BaseModel):
    username: str
    platform: SocialPlatform
    id: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_url: Optional[str] = None
    is_verified: bool = False

class SocialComment(BaseModel):
    id: str
    author: SocialAuthor
    text: str
    created_at: Optional[datetime] = None
    like_count: int = 0

class SocialPost(BaseModel):
    id: str
    platform: SocialPlatform
    author: SocialAuthor
    content: str  # Caption or Tweet text
    url: str
    created_at: Optional[datetime] = None
    
    # Media
    media_urls: List[str] = Field(default_factory=list) # Images/Videos
    media_type: str = "text" # image, video, carousel, text
    
    # Interactions
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    
    # Context
    comments: List[SocialComment] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict) # Original payload

class SocialProfile(BaseModel):
    username: str
    platform: SocialPlatform
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    recent_posts: List[SocialPost] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)

class ActionDecision(BaseModel):
    should_act: bool
    action_type: str = "comment" # comment, like, share
    content: Optional[str] = None # The comment text
    reasoning: Optional[str] = None
    platform: Optional[SocialPlatform] = None
