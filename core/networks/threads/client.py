"""
Playwright-based Threads Client
"""
from core.interfaces import SocialNetworkClient
from core.models import SocialPost, SocialAuthor, SocialPlatform, SocialComment, SocialProfile
from typing import Union, List, Optional, Dict, Any
import logging
import random
import time
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright
from core.browser_manager import BrowserManager

from config.settings import settings

logger = logging.getLogger(__name__)

class ThreadsClient(SocialNetworkClient):
    """
    Threads client using Playwright.
    """
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session_path = Path("browser_state")
        self._is_logged_in = False
    
    @property
    def platform(self) -> SocialPlatform:
        return SocialPlatform.THREADS
    
    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Human-like random delay."""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def start(self) -> bool:
        """Initialize browser and load session."""
        try:
            self.playwright = BrowserManager.get_playwright()
            
            self.browser = self.playwright.chromium.launch(
                headless=settings.DEBUG_HEADLESS,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            state_file = self.session_path / "state_threads.json"
            if state_file.exists():
                logger.info("Loading existing Threads session...")
                self.context = self.browser.new_context(
                    storage_state=str(state_file),
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/Sao_Paulo'
                )
            else:
                logger.warning("No Threads session found!")
                self.context = self.browser.new_context(
                    viewport={'width': 1280, 'height': 800}
                )
            
            self.page = self.context.new_page()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False

    def login(self) -> bool:
        """Check login status."""
        if not self.page:
            if not self.start():
                return False
        
        try:
            logger.info("Checking Threads login status...")
            self.page.goto('https://www.threads.net/', timeout=30000)
            self._random_delay(2, 4)
            
            try:
                # Check for Home or Post button
                self.page.wait_for_selector('svg[aria-label="Home"], a[href="/"] svg[aria-label="Home"]', timeout=5000)
                logger.info("Threads: Already logged in!")
                self._is_logged_in = True
                return True
            except:
                logger.warning("Threads: Not logged in. Please run scripts/login_threads.py")
                return False
                
        except Exception as e:
            logger.error(f"Threads login check failed: {e}")
            return False

    def stop(self):
        """Cleanup."""
        if self.context:
            try:
                self.session_path.mkdir(exist_ok=True)
            except:
                pass
        if self.browser:
            self.browser.close()

    def get_post_details(self, post_id: str) -> Optional[SocialPost]:
        """Fetches post details."""
        if not self._is_logged_in:
            return None
            
        try:
            url = f"https://www.threads.net/post/{post_id}"
            self.page.goto(url, timeout=30000)
            self._random_delay(2, 3)
            
            # Selectors (Threads specific)
            # Need to implement these based on inspection or generic
            # Threads uses a lot of dynamic classes too
            
            # For now, placeholder
            return SocialPost(
                id=post_id,
                platform=self.platform,
                author=SocialAuthor(username="unknown", platform=self.platform),
                content="Placeholder content",
                url=url,
                media_urls=[],
                media_type="text"
            )
            
        except Exception as e:
            logger.error(f"Error fetching threads post {post_id}: {e}")
            return None

    def like_post(self, post: Union[SocialPost, str]) -> bool:
        """Likes a post."""
        return True

    def post_comment(self, post: Union[SocialPost, str], text: str) -> bool:
        """Replies to a post."""
        return True
    
    def get_user_latest_posts(self, username: str, limit: int = 5) -> List[SocialPost]:
        """Fetches latest posts from a user's threads profile."""
        if not self._is_logged_in: return []
        
        try:
            url = f"https://www.threads.net/@{username}"
            logger.info(f"Visiting Threads profile: {url}")
            self.page.goto(url, timeout=30000)
            self._random_delay(2, 4)
            
            # Scroll
            for _ in range(2):
                self.page.mouse.wheel(0, 500)
                self._random_delay(0.5, 1)

            # Threads structure is complex/dynamic. We look for links containing "/post/"
            # A generic strategy: find all 'a' tags with href containing '/post/'
            # Then find the parent text container.
            
            # Selector for post containers (approximate)
            # Threads generic strategy: Search for SVG icons or specific aria-labels doesn't work well over time.
            # We'll grab links and try to extract content relative to them.
            
            post_links = self.page.query_selector_all('a[href*="/post/"]')
            
            results = []
            seen_ids = set()
            
            for link in post_links:
                if len(results) >= limit: break
                
                href = link.get_attribute('href')
                if not href: continue
                
                # /@username/post/ID
                try:
                    parts = href.strip('/').split('/')
                    if 'post' in parts:
                        idx = parts.index('post')
                        if idx + 1 < len(parts):
                            post_id = parts[idx+1]
                            
                            if post_id in seen_ids: continue
                            seen_ids.add(post_id)
                            
                            # Content extraction is hard without robust selectors
                            # For V1, we'll try to get the innerText of the link's parent's parent
                            # or just leave empty and let the visual agent fill it if needed? 
                            # But NetBotAgent needs text.
                            
                            # Try to find a text block near the link
                            content = "Content extraction pending visual analysis"
                            
                            # Optimization: The ink usually WRAPS the timestamp or the post itself.
                            # If it wraps the timestamp (common in social), the content is in a sibling.
                            
                            results.append(SocialPost(
                                id=post_id,
                                platform=self.platform,
                                author=SocialAuthor(username=username, platform=self.platform),
                                content=content, # Placeholder for now
                                url=f"https://www.threads.net{href}",
                                media_type="text"
                            ))
                except:
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error fetching threads for {username}: {e}")
            return []

    def search_posts(self, query: str, limit: int = 5) -> List[SocialPost]:
        """Searches for posts on Threads."""
        if not self._is_logged_in: return []
        
        try:
            url = f"https://www.threads.net/search?q={query}"
            logger.info(f"Searching Threads: {url}")
            self.page.goto(url, timeout=30000)
            self._random_delay(2, 4)
            
            # Same logic as profile
            post_links = self.page.query_selector_all('a[href*="/post/"]')
            results = []
            seen_ids = set()
            
            for link in post_links:
                if len(results) >= limit: break
                href = link.get_attribute('href')
                if not href: continue
                
                try:
                    parts = href.strip('/').split('/')
                    if 'post' in parts:
                        idx = parts.index('post')
                        if idx + 1 < len(parts):
                            post_id = parts[idx+1]
                            if post_id in seen_ids: continue
                            seen_ids.add(post_id)
                            
                            results.append(SocialPost(
                                id=post_id,
                                platform=self.platform,
                                author=SocialAuthor(username="unknown", platform=self.platform),
                                content="Search Result",
                                url=f"https://www.threads.net{href}",
                                media_type="text"
                            ))
                except: continue
                
            return results
        except Exception as e:
            logger.error(f"Error searching threads {query}: {e}")
            return []

    def get_profile_data(self, username: str) -> Optional[SocialProfile]:
        """Fetches Threads profile data."""
        # Minimal implementation
        return SocialProfile(
            username=username,
            platform=self.platform,
            bio="Threads Bio",
            recent_posts=[]
        )
