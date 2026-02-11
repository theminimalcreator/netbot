import requests
from typing import Optional, List, Dict, Any
from core.interfaces import SocialNetworkClient
from core.models import SocialPlatform, SocialPost, SocialAuthor, SocialComment, SocialProfile
from config.settings import settings
from core.logger import logger

from playwright.sync_api import Browser, BrowserContext, Page, Playwright
from core.browser_manager import BrowserManager
from pathlib import Path

class DevToClient(SocialNetworkClient):
    BASE_URL = "https://dev.to/api"
    REQUEST_TIMEOUT = 15

    @property
    def platform(self) -> SocialPlatform:
        return SocialPlatform.DEVTO

    def __init__(self):
        self.api_key = settings.DEVTO_API_KEY
        self.headers = {
            "api-key": self.api_key,
            "User-Agent": "NetBot/2.0"
        }
        # Browser Automation
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session_path = settings.BASE_DIR / "browser_state"
        self._is_browser_active = False

    def login(self) -> bool:
        """
        Dev.to uses API Key, so specific login flow isn't strictly necessary,
        but we can check if the key is valid by fetching the authenticated user.
        """
        if not self.api_key:
            logger.error("[DevTo] No API Key provided.")
            return False
            
        try:
            response = requests.get(f"{self.BASE_URL}/users/me", headers=self.headers, timeout=self.REQUEST_TIMEOUT)
            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"[DevTo] Authenticated as {user_data.get('username')}")
                return True
            else:
                logger.error(f"[DevTo] Authentication failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"[DevTo] Login error: {e}")
            return False

    def _start_browser(self) -> bool:
        """Starts the browser and loads the session for interactions."""
        if self._is_browser_active and self.page:
            return True
            
        try:
            logger.info("[DevTo] Starting browser for interaction...")
            self.playwright = BrowserManager.get_playwright()
            
            self.browser = self.playwright.chromium.launch(
                headless=settings.DEBUG_HEADLESS,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            state_file = self.session_path / "state_devto.json"
            if state_file.exists():
                logger.info("[DevTo] Loading existing Dev.to session...")
                self.context = self.browser.new_context(
                    storage_state=str(state_file),
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US'
                )
            else:
                logger.warning("[DevTo] No Dev.to session found! Interactions may fail (User must be logged in).")
                self.context = self.browser.new_context(viewport={'width': 1280, 'height': 800})
            
            self.page = self.context.new_page()
            self._is_browser_active = True
            return True
            
        except Exception as e:
            logger.error(f"[DevTo] Failed to start browser: {e}")
            return False

    def stop(self):
        """Closes browser resources."""
        if self.context:
            try:
                self.context.close()
            except: pass
        if self.browser:
            try:
                self.browser.close()
            except: pass
        
        # Clear references
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        self._is_browser_active = False

    def get_post_details(self, post_id: str) -> Optional[SocialPost]:
        """Fetches article details and recent comments for context."""
        try:
            # 1. Fetch Article Details
            response = requests.get(f"{self.BASE_URL}/articles/{post_id}", headers=self.headers, timeout=self.REQUEST_TIMEOUT)
            if response.status_code != 200:
                logger.error(f"[DevTo] Failed to fetch article {post_id}: {response.status_code}")
                return None
            
            data = response.json()
            
            # 2. Fetch Comments (for context)
            comments = self._fetch_comments(post_id)

            author = SocialAuthor(
                username=data["user"]["username"],
                platform=SocialPlatform.DEVTO,
                id=str(data["user"]["user_id"]),
                display_name=data["user"]["name"],
                profile_url=f"https://dev.to/{data['user']['username']}",
                bio=data["user"].get("github_username") # using github as bio proxy or fetch profile
            )

            return SocialPost(
                id=str(data["id"]),
                platform=SocialPlatform.DEVTO,
                author=author,
                content=data.get("body_markdown", "")[:5000], # Limit content for context window
                url=data["url"],
                created_at=None, # Parse if needed
                media_urls=[data["cover_image"]] if data.get("cover_image") else [],
                media_type="image" if data.get("cover_image") else "text",
                like_count=data["public_reactions_count"],
                comment_count=data["comments_count"],
                comments=comments,
                raw_data=data
            )
            
        except Exception as e:
            logger.error(f"[DevTo] Error getting post details: {e}")
            return None

    def _fetch_comments(self, article_id: str, limit: int = 5) -> List[SocialComment]:
        """Fetches top-level comments for context."""
        try:
            response = requests.get(f"{self.BASE_URL}/comments?a_id={article_id}", headers=self.headers, timeout=self.REQUEST_TIMEOUT)
            if response.status_code == 200:
                comments_data = response.json()
                # Dev.to returns a tree. We just take top-level for now.
                # Sort by latest or top? API returns threaded.
                
                parsed_comments = []
                for c in comments_data[:limit]:
                    author = SocialAuthor(
                        username=c["user"]["username"],
                        platform=SocialPlatform.DEVTO,
                        id=str(c["user"]["user_id"])
                    )
                    parsed_comments.append(SocialComment(
                        id=c["id_code"],
                        author=author,
                        text=self._clean_html(c.get("body_html", "")),
                        like_count=0 # API doesn't expose this easily in list
                    ))
                return parsed_comments
            return []
        except Exception as e:
            logger.warning(f"[DevTo] Failed to fetch comments: {e}")
            return []

    def _clean_html(self, raw_html: str) -> str:
        """Simple HTML cleaner for comments (Dev.to returns body_html for comments)."""
        import re
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext.strip()

    def like_post(self, post: SocialPost) -> bool:
        """Reacts to an article using Playwright."""
        if not self._start_browser():
            return False

        try:
            logger.info(f"[DevTo] Liking post {post.id} via Browser...")
            # Use explicit timeout
            self.page.goto(post.url, timeout=self.REQUEST_TIMEOUT * 1000)
            self.page.wait_for_load_state("domcontentloaded")

            # Like button is usually #reaction-butt-like
            # We look for the main heart button
            
            # Check if button exists
            if not self.page.is_visible('#reaction-butt-like'):
                logger.warning(f"[DevTo] Like button not found on {post.url}")
                return False
            
            # Check if already liked
            # The button usually has 'user-activated' class when liked
            is_liked = self.page.evaluate("document.querySelector('#reaction-butt-like').classList.contains('user-activated')")
            
            if is_liked:
                logger.info(f"[DevTo] Already liked {post.id}")
                return True
            
            self.page.click('#reaction-butt-like')
            self.page.wait_for_timeout(1000)
            
            # Verify
            is_liked_now = self.page.evaluate("document.querySelector('#reaction-butt-like').classList.contains('user-activated')")
            if is_liked_now:
                 logger.info(f"[DevTo] Successfully liked {post.id}")
                 return True
            else:
                 logger.warning(f"[DevTo] Like check failed for {post.id} after click.")
                 return False 

        except Exception as e:
            logger.error(f"[DevTo] Error liking via browser: {e}")
            return False

    def post_comment(self, post: SocialPost, text: str) -> bool:
        """Posts a comment using Playwright."""
        if not self._start_browser():
            return False

        try:
            logger.info(f"[DevTo] Commenting on {post.id} via Browser...")
            # If we are already on the page from like_post, we might save a nav, 
            # but safer to ensure we are on the right URL
            if self.page.url != post.url:
                # Use explicit timeout
                self.page.goto(post.url, timeout=self.REQUEST_TIMEOUT * 1000)
                self.page.wait_for_load_state("domcontentloaded")
            
            # 1. Fill Textarea
            textarea_sel = 'textarea[name="comment[body_markdown]"]'
            
            # Sometimes textarea is hidden behind "Add to the discussion" button?
            # Usually it's visible at the bottom or we skip to it.
            # Let's try to focus it.
            
            if not self.page.is_visible(textarea_sel):
                logger.info("[DevTo] Comment unavailable or hidden.")
                return False
                
            self.page.fill(textarea_sel, text)
            
            # 2. Submit
            # Button might be "Submit" or with class .crayons-btn
            submit_sel = 'button.crayons-btn:has-text("Submit")'
            
            self.page.click(submit_sel)
            self.page.wait_for_timeout(2500)
            
            logger.info(f"[DevTo] Comment submitted on {post.id}")
            return True

        except Exception as e:
            logger.error(f"[DevTo] Error commenting via browser: {e}")
            return False



    def search_posts(self, query: str, limit: int = 10) -> List[SocialPost]:
        """Searches articles by tag."""
        try:
            # Discovery uses query as tag
            params = {
                "tag": query,
                "per_page": limit,
                "state": "fresh" # fresh checking? or rising.
            }
            response = requests.get(f"{self.BASE_URL}/articles", params=params, headers=self.headers, timeout=self.REQUEST_TIMEOUT)
            if response.status_code == 200:
                return self._parse_articles_list(response.json())
            return []
        except Exception as e:
            logger.error(f"[DevTo] Error searching: {e}")
            return []

    def get_user_latest_posts(self, username: str, limit: int = 5) -> List[SocialPost]:
        """Fetches latest posts from a user."""
        try:
            params = {
                "username": username,
                "per_page": limit
            }
            response = requests.get(f"{self.BASE_URL}/articles", params=params, headers=self.headers, timeout=self.REQUEST_TIMEOUT)
            if response.status_code == 200:
                return self._parse_articles_list(response.json())
            return []
        except Exception as e:
            logger.error(f"[DevTo] Error fetching user posts: {e}")
            return []
            
    def _parse_articles_list(self, articles_data: List[Dict]) -> List[SocialPost]:
        posts = []
        for data in articles_data:
            if data.get("type_of") != "article":
                continue
                
            author = SocialAuthor(
                username=data["user"]["username"],
                platform=SocialPlatform.DEVTO,
                id=str(data["user"]["user_id"]),
                display_name=data["user"]["name"],
                profile_url=f"https://dev.to/{data['user']['username']}"
            )
            
            post = SocialPost(
                id=str(data["id"]),
                platform=SocialPlatform.DEVTO,
                author=author,
                content=data["title"] + "\n" + data["description"], # Content is limited in list view
                url=data["url"],
                created_at=None,
                media_urls=[data["cover_image"]] if data.get("cover_image") else [],
                media_type="image" if data.get("cover_image") else "text",
                like_count=data["public_reactions_count"],
                comment_count=data["comments_count"],
                raw_data=data
            )
            posts.append(post)
        return posts
        
    def get_profile_data(self, username: str) -> Optional[SocialProfile]:
        try:
            # Use the correct endpoint for fetching user by username
            response = requests.get(
                f"{self.BASE_URL}/users/by_username", 
                params={"url": username}, 
                headers=self.headers, 
                timeout=self.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                return SocialProfile(
                    username=data.get("username", username),
                    platform=SocialPlatform.DEVTO,
                    bio=data.get("summary") or data.get("website_url") or "",
                    recent_posts=[] 
                )
            
            logger.warning(f"[DevTo] Failed to fetch profile {username}: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"[DevTo] Error fetching profile {username}: {e}")
            return None
