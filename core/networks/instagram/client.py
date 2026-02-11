"""
Playwright-based Instagram Client

Uses a real browser for all Instagram operations:
- Session management with persistent context
- Post extraction (caption, media, comments)
- Comment posting
- Profile/hashtag browsing for discovery
"""
from core.interfaces import SocialNetworkClient
from core.models import SocialPost, SocialAuthor, SocialPlatform, SocialComment, SocialProfile
from typing import Union
import os
import json
import logging
import random
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import unquote

from playwright.sync_api import Browser, BrowserContext, Page, Playwright
from core.browser_manager import BrowserManager

from config.settings import settings

logger = logging.getLogger(__name__)


class InstagramClient(SocialNetworkClient):
    """
    Instagram client using Playwright for browser automation.
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
        return SocialPlatform.INSTAGRAM
    
    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Human-like random delay."""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def start(self) -> bool:
        """Initialize browser and load session."""
        try:
            self.playwright = BrowserManager.get_playwright()
            
            # Launch browser
            self.browser = self.playwright.chromium.launch(
                headless=settings.DEBUG_HEADLESS,  # Set DEBUG_HEADLESS=False to see browser
                args=['--disable-blink-features=AutomationControlled']
            )
            
            # Try to load existing state
            if self.session_path.exists():
                logger.info("Loading existing browser session...")
                self.context = self.browser.new_context(
                    storage_state=str(self.session_path / "state.json"),
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/Sao_Paulo'
                )
            else:
                logger.info("Creating new browser context...")
                self.context = self.browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/Sao_Paulo'
                )
            
            self.page = self.context.new_page()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False
    
    def login(self) -> bool:
        """
        Check if already logged in, or perform interactive login.
        """
        if not self.page:
            if not self.start():
                return False
        
        try:
            # Navigate to Instagram
            logger.info("Checking login status...")
            self.page.goto('https://www.instagram.com/', timeout=30000)
            self._random_delay(2, 4)
            
            # Check if we're logged in by looking for the home/profile elements
            try:
                self.page.wait_for_selector(
                    'svg[aria-label="Home"], a[href="/direct/inbox/"]',
                    timeout=5000
                )
                logger.info("Already logged in!")
                self._is_logged_in = True
                self._save_state()
                return True
            except:
                pass
            
            # Not logged in - need interactive login
            logger.warning("Not logged in. Starting interactive login...")
            
            # Switch to non-headless for interactive login
            self.stop()
            return self._interactive_login()
            
        except Exception as e:
            logger.error(f"Login check failed: {e}")
            return False
    
    def _interactive_login(self) -> bool:
        """Opens visible browser for user to login manually."""
        try:
            self.playwright = BrowserManager.get_playwright()
            self.browser = self.playwright.chromium.launch(
                headless=False,  # User needs to see this
                args=['--disable-blink-features=AutomationControlled']
            )
            
            self.context = self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/Sao_Paulo'
            )
            
            self.page = self.context.new_page()
            self.page.goto('https://www.instagram.com/accounts/login/')
            
            logger.info("Please login in the browser window...")
            
            # Wait for successful login (up to 5 minutes)
            self.page.wait_for_selector(
                'svg[aria-label="Home"], a[href="/direct/inbox/"]',
                timeout=300000
            )
            
            logger.info("Login successful!")
            self._is_logged_in = True
            self._save_state()
            
            # Close and reopen headless
            self.stop()
            return self.start() and self.login()
            
        except Exception as e:
            logger.error(f"Interactive login failed: {e}")
            return False
    
    def _save_state(self):
        """Save browser state for session persistence."""
        if self.context:
            self.session_path.mkdir(exist_ok=True)
            self.context.storage_state(path=str(self.session_path / "state.json"))
            logger.info("Browser state saved.")
    
    def stop(self):
        """Close browser and cleanup."""
        if self.context:
            try:
                self._save_state()
            except:
                pass
        if self.browser:
            self.browser.close()
        
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
    
    def get_user_latest_medias(self, username: str, amount: int = 3) -> List[Dict[str, Any]]:
        """Fetches latest posts from a user's profile."""
        if not self._is_logged_in:
            logger.warning("Not logged in!")
            return []
        
        try:
            logger.info(f"Fetching posts from @{username}...")
            self.page.goto(f'https://www.instagram.com/{username}/', timeout=30000)
            self._random_delay(3, 5)
            
            # Try multiple selectors for posts
            post_selectors = [
                'a[href*="/p/"]',
                'article a[href*="/p/"]',
                'div[style*="flex"] a[href*="/p/"]',
                'main a[href*="/p/"]'
            ]
            
            post_links = []
            for selector in post_selectors:
                try:
                    self.page.wait_for_selector(selector, timeout=5000)
                    post_links = self.page.query_selector_all(selector)
                    if post_links:
                        logger.info(f"Found {len(post_links)} posts with selector: {selector}")
                        break
                except:
                    continue
            
            if not post_links:
                logger.warning(f"No posts found for @{username}")
                return []
            
            # IMPORTANT: Extract ALL hrefs FIRST before navigating
            # Otherwise navigation destroys the element context
            post_codes = []
            for link in post_links[:amount]:
                try:
                    href = link.get_attribute('href')
                    if href and '/p/' in href:
                        post_code = href.split('/p/')[1].rstrip('/').split('/')[0]
                        post_codes.append(post_code)
                except:
                    continue
            
            logger.info(f"Extracted {len(post_codes)} post codes: {post_codes}")
            
            # Now navigate to each post
            results = []
            for post_code in post_codes:
                post_data = self._get_post_data(post_code)
                if post_data:
                    results.append(post_data)
                    self._random_delay(1, 2)
            
            return results
            
        except Exception as e:
            logger.error(f"Error fetching posts from @{username}: {e}")
            return []
    
    def get_hashtag_top_medias(self, hashtag: str, amount: int = 3) -> List[Dict[str, Any]]:
        """Fetches top posts from a hashtag."""
        if not self._is_logged_in:
            logger.warning("Not logged in!")
            return []
        
        try:
            logger.info(f"Fetching posts from #{hashtag}...")
            self.page.goto(f'https://www.instagram.com/explore/tags/{hashtag}/', timeout=30000)
            self._random_delay(3, 5)
            
            # Try multiple selectors for posts
            post_selectors = [
                'a[href*="/p/"]',
                'article a[href*="/p/"]',
                'div[style*="flex"] a[href*="/p/"]',
                'main a[href*="/p/"]'
            ]
            
            post_links = []
            for selector in post_selectors:
                try:
                    self.page.wait_for_selector(selector, timeout=5000)
                    post_links = self.page.query_selector_all(selector)
                    if post_links:
                        logger.info(f"Found {len(post_links)} posts with selector: {selector}")
                        break
                except:
                    continue
            
            if not post_links:
                logger.warning(f"No posts found for #{hashtag}")
                return []
            
            # IMPORTANT: Extract ALL hrefs FIRST before navigating
            post_codes = []
            for link in post_links[:amount]:
                try:
                    href = link.get_attribute('href')
                    if href and '/p/' in href:
                        post_code = href.split('/p/')[1].rstrip('/').split('/')[0]
                        post_codes.append(post_code)
                except:
                    continue
            
            logger.info(f"Extracted {len(post_codes)} post codes: {post_codes}")
            
            # Now navigate to each post
            results = []
            for post_code in post_codes:
                post_data = self._get_post_data(post_code)
                if post_data:
                    results.append(post_data)
                    self._random_delay(1, 2)
            
            return results
            
        except Exception as e:
            logger.error(f"Error fetching posts from #{hashtag}: {e}")
            return []
    
    def _get_post_data(self, post_code: str) -> Optional[Dict[str, Any]]:
        """Navigates to a post and extracts its data."""
        try:
            self.page.goto(f'https://www.instagram.com/p/{post_code}/', timeout=30000)
            self._random_delay(2, 3)
            
            # --- Extract Username ---
            username = ""
            # Priority 1: The standard author link in header
            header_author = self.page.query_selector('header a._a6hd, header a[role="link"]')
            
            if header_author:
                username = header_author.inner_text().strip()
            
            if not username:
                # Fallback: Check URL/Title or other links
                try:
                    meta_author = self.page.query_selector('meta[property="og:title"]')
                    if meta_author:
                        content = meta_author.get_attribute('content')
                        if content and ' on Instagram' in content:
                            username = content.split(' on Instagram')[0].strip()
                except:
                    pass

            logger.info(f"[{post_code}] Extracted username: '{username}'")
            
            # --- Extract Caption ---
            caption = ""
            # Priority 1: The main caption container (often h1 or first item in comments list)
            # Instagram often puts caption in a span inside a div._a9zs or similar
            
            # Try H1 first (often used for accessibility)
            h1_el = self.page.query_selector('h1')
            if h1_el:
                caption = h1_el.inner_text()
            
            if not caption:
                # Try standard caption container class
                caption_el = self.page.query_selector('div._a9zs span, span._ap3a._aaco._aacu._aacx._aad7._aade')
                if caption_el:
                    caption = caption_el.inner_text()
            
            if not caption:
                # Fallback: Get text from the first comment-like structure if it matches author
                try:
                    first_comment_area = self.page.query_selector('ul._a9z6, ul.x78zum5, div.x78zum5.xdt5ytf')
                    if first_comment_area:
                        # Sometimes the first li is the caption
                        first_item = first_comment_area.query_selector('li')
                        if first_item:
                            text_el = first_item.query_selector('span._aacl._aaco._aacu._aacx._aad7._aade, span')
                            if text_el:
                                caption = text_el.inner_text()
                except:
                    pass
            
            if not caption:
                # Ultimate Fallback: Open Graph Description
                # Format: "Likes, Comments - Username on Date: \"Caption\"."
                try:
                    og_desc_el = self.page.query_selector('meta[property="og:description"]')
                    if og_desc_el:
                        og_content = og_desc_el.get_attribute('content')
                        if og_content and ': "' in og_content:
                            # Extract everything after the first occurrences of ': "'
                            # and remove the trailing '"' or '".'
                            parts = og_content.split(': "', 1)
                            if len(parts) > 1:
                                raw_unique_caption = parts[1]
                                # Remove trailing quote and dot if present
                                if raw_unique_caption.endswith('".'):
                                    caption = raw_unique_caption[:-2]
                                elif raw_unique_caption.endswith('"'):
                                    caption = raw_unique_caption[:-1]
                                else:
                                    caption = raw_unique_caption
                                logger.info(f"[{post_code}] Extracted caption from og:description")
                except Exception as e:
                    logger.warning(f"Failed to extract from og:description: {e}")

            # Log the caption for debugging
            log_caption = caption[:100].replace('\n', ' ') + "..." if len(caption) > 100 else caption.replace('\n', ' ')
            logger.info(f"[{post_code}] Extracted caption: '{log_caption}'")
            
            # --- Extract Image URL ---
            image_url = None
            img_selectors = [
                'div._aagv img',           # Standard post image
                'article img[src*="instagram"]',
                'img[src*="cdninstagram"]',
                'div[role="button"] img'
            ]
            for sel in img_selectors:
                try:
                    el = self.page.query_selector(sel)
                    if el:
                        src = el.get_attribute('src')
                        if src and 'http' in src:
                            image_url = src
                            break
                except:
                    continue
            
            if not image_url:
                # Fallback: Open Graph Image
                try:
                    og_image_el = self.page.query_selector('meta[property="og:image"]')
                    if og_image_el:
                        og_image_url = og_image_el.get_attribute('content')
                        if og_image_url and 'http' in og_image_url:
                            image_url = og_image_url
                            logger.info(f"[{post_code}] Extracted image URL from og:image")
                except:
                    pass
            
            logger.info(f"[{post_code}] Extracted image URL: {image_url[:50] if image_url else 'None'}...")
            
            # --- Extract Comments ---
            comments = self._get_post_comments()
            
            return {
                "media_id": post_code,
                "pk": post_code,
                "code": post_code,
                "username": username,
                "caption": caption,
                "image_url": image_url,
                "taken_at": None,
                "media_type": 1,
                "comments": comments
            }
            
        except Exception as e:
            logger.error(f"Error extracting post {post_code}: {e}")
            return None
    
    def _get_post_comments(self, amount: int = 5) -> List[Dict[str, str]]:
        """Extracts comments from the current post page."""
        comments = []
        try:
            # Comments are usually in a scrollable area
            comment_elements = self.page.query_selector_all('ul ul li')
            
            for comment_el in comment_elements[:amount]:
                try:
                    username_el = comment_el.query_selector('a[href*="/"]')
                    text_el = comment_el.query_selector('span')
                    
                    if username_el and text_el:
                        username = username_el.get_attribute('href', '').strip('/').split('/')[-1]
                        text = text_el.inner_text()
                        if username and text:
                            comments.append({"username": username, "text": text})
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error extracting comments: {e}")
        
        return comments
    
    def get_post_details(self, post_id: str) -> Optional[SocialPost]:
        """Fetches full details of a specific post."""
        data = self._get_post_data(post_id)
        if not data:
            return None
            
        # Convert to SocialPost
        return SocialPost(
            id=data['code'],
            platform=self.platform,
            author=SocialAuthor(
                username=data['username'],
                platform=self.platform
            ),
            content=data['caption'],
            url=f"https://www.instagram.com/p/{data['code']}/",
            media_urls=[data['image_url']] if data.get('image_url') else [],
            media_type="image",
            comments=[
                SocialComment(
                    id=f"temp_id_{i}",
                    author=SocialAuthor(username=c['username'], platform=self.platform),
                    text=c['text']
                ) for i, c in enumerate(data.get('comments', []))
            ],
            raw_data=data
        )

    def get_user_latest_posts(self, username: str, limit: int = 5) -> List[SocialPost]:
        """Fetches latest posts from a user's profile."""
        raw_posts = self.get_user_latest_medias(username, amount=limit)
        return [self._map_to_social_post(p) for p in raw_posts if p]

    def get_profile_data(self, username: str) -> Optional[SocialProfile]:
        """Fetches profile information (bio, stats) and recent posts."""
        if not self._is_logged_in:
            logger.warning("Not logged in!")
            return None
            
        try:
            logger.info(f"Fetching profile data for @{username}...")
            # We assume get_user_latest_medias handles the navigation, but it doesn't extract bio.
            # So we navigate here explicitly or modify get_user_latest_medias.
            # Let's navigate here to be safe and extract bio first.
            self.page.goto(f'https://www.instagram.com/{username}/', timeout=30000)
            self._random_delay(3, 5)
            
            # --- Extract Bio ---
            bio = ""
            # Structural selector: Header -> Section -> Div (last child usually) -> Span
            try:
                # Try finding the bio via text content if specific classes fail
                # But let's try the stable structural approach first
                # Header usually contains the profile info
                header = self.page.query_selector('header')
                if header:
                    # The bio is often in a span within the last div of the section
                    # Or we can look for the specific classes if they are semi-stable
                    # Found in research: span._ap3a._aaco._aacu._aacx._aad7._aade
                    bio_el = header.query_selector('span._ap3a._aaco._aacu._aacx._aad7._aade')
                    if not bio_el:
                         # Fallback: look for any span with substantial text that isn't the username
                         spans = header.query_selector_all('span')
                         for span in spans:
                             text = span.inner_text()
                             if len(text) > 10 and username not in text: # Heuristic
                                 bio = text
                                 break
                    else:
                        bio = bio_el.inner_text()
            except Exception as e:
                logger.warning(f"Failed to extract bio: {e}")
            
            logger.info(f"Extracted Bio: {bio[:50]}...")
            
            # --- Extract Stats (Optional) ---
            follower_count = None
            try:
                # Stats are usually in an unordered list (ul) in the header
                # Li: Posts, Followers, Following
                # Selector: header ul li:nth-child(2)
                stats_ul = self.page.query_selector('header ul')
                if stats_ul:
                    lis = stats_ul.query_selector_all('li')
                    if len(lis) >= 2:
                        followers_text = lis[1].inner_text() # e.g. "1.2M followers"
                        # Simple cleanup: "1.2M followers" -> parse
                        # For now just storing it might be complex, skipping exact number parsing
                        pass
            except:
                pass

            # --- Extract Recent Posts ---
            # We can reuse get_user_latest_medias logic but we need to avoid re-navigating if possible
            # However, get_user_latest_medias navigates to the profile again. 
            # To avoid code duplication, we will just call it.
            # It's slightly inefficient (double nav if we don't refactor) but Playwright caches content often.
            # Actually, get_user_latest_medias does: page.goto -> extract hrefs -> page.goto(post)
            # So calling it is fine.
            
            latest_posts_social = self.get_user_latest_posts(username, limit=10)
            
            return SocialProfile(
                username=username,
                platform=self.platform,
                bio=bio,
                recent_posts=latest_posts_social,
                post_count=len(latest_posts_social) # Just what we fetched
            )
            
        except Exception as e:
            logger.error(f"Error fetching profile data for @{username}: {e}")
            return None

    def search_posts(self, query: str, limit: int = 10) -> List[SocialPost]:
        """Searches for posts (hashtags)."""
        # Remove # if present
        tag = query.replace("#", "")
        raw_posts = self.get_hashtag_top_medias(tag, amount=limit)
        return [self._map_to_social_post(p) for p in raw_posts if p]

    def _map_to_social_post(self, data: Dict[str, Any]) -> SocialPost:
        """Helper to convert raw dict to SocialPost."""
        return SocialPost(
            id=data['code'],
            platform=self.platform,
            author=SocialAuthor(
                username=data['username'],
                platform=self.platform
            ),
            content=data['caption'],
            url=f"https://www.instagram.com/p/{data['code']}/",
            media_urls=[data['image_url']] if data.get('image_url') else [],
            media_type="image",
            comments=[
                SocialComment(
                    id=f"temp_id_{i}",
                    author=SocialAuthor(username=c['username'], platform=self.platform),
                    text=c['text']
                ) for i, c in enumerate(data.get('comments', []))
            ],
            raw_data=data
        )

    def get_media_info(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Deprecated: Use get_post_details instead."""
        return self._get_post_data(media_id)
    
    def get_media_comments(self, media_id: str, amount: int = 5) -> List[Dict[str, str]]:
        """Fetches comments from a media."""
        # Navigate to post first
        self.page.goto(f'https://www.instagram.com/p/{media_id}/', timeout=30000)
        self._random_delay(1, 2)
        return self._get_post_comments(amount)
    
    def like_post(self, post: Union[SocialPost, str]) -> bool:
        """Likes a post."""
        media_id = post.id if isinstance(post, SocialPost) else post
        
        if settings.dry_run:
            logger.info(f"[DRY RUN] Would like post {media_id}")
            return True
            
        try:
            # Make sure we're on the post page
            if media_id not in self.page.url:
                self.page.goto(f'https://www.instagram.com/p/{media_id}/', timeout=30000)
                self._random_delay(2, 3)
            
            # Check if already liked
            # Liked state usually has a specific color (red) or aria-label change
            like_button_selectors = [
                'svg[aria-label="Like"]', 
                # Unliked state usually has these labels. Liked has "Unlike"
            ]
            
            # If we find an "Unlike" or "Descurtir" button, it's already liked
            already_liked_selectors = [
                'svg[aria-label="Unlike"]'
            ]
            
            for selector in already_liked_selectors:
                if self.page.query_selector(selector):
                    logger.info(f"Post {media_id} already liked.")
                    return True

            # Find the Like button
            like_btn = None
            for selector in like_button_selectors:
                btn = self.page.query_selector(selector)
                if btn:
                    like_btn = btn
                    break
            
            if like_btn:
                # Click parent usually to be safe, or the svg itself
                like_btn.click()
                logger.info(f"Liked post {media_id}")
                self._random_delay(1, 2)
                return True
            else:
                logger.warning("Could not find Like button.")
                return False
                
        except Exception as e:
            logger.error(f"Error liking post {media_id}: {e}")
            return False
    
    def post_comment(self, post: Union[SocialPost, str], text: str) -> bool:
        """Posts a comment on a media."""
        media_id = post.id if isinstance(post, SocialPost) else post
        
        if settings.dry_run:
            logger.info(f"[DRY RUN] Would comment on {media_id}: {text}")
            return True
        
        try:
            # Make sure we're on the post page
            if media_id not in self.page.url:
                self.page.goto(f'https://www.instagram.com/p/{media_id}/', timeout=30000)
                self._random_delay(2, 4)
            
            # 1. First, try to click the comment icon to activate/focus the area
            # This is improved to handle both English and Portuguese
            try:
                comment_icon_selector = 'svg[aria-label="Comment"], span[class*="_aamx"]'
                self.page.wait_for_selector(comment_icon_selector, timeout=5000)
                comment_icons = self.page.query_selector_all(comment_icon_selector)
                
                # Usually the first one is the main action button
                if comment_icons:
                    comment_icons[0].click()
                    self._random_delay(0.5, 1.5)
            except Exception as e:
                logger.debug(f"Could not click comment icon: {e}")

            # 2. Now look for the textarea
            # It might have been dynamically inserted or focused
            textarea_selector = 'textarea[aria-label*="omment"], textarea[placeholder*="omment"], form textarea'
            
            try:
                self.page.wait_for_selector(textarea_selector, timeout=5000, state='visible')
                comment_area = self.page.query_selector(textarea_selector)
            except:
                logger.error("Could not find comment textarea even after clicking icon.")
                return False
            
            if not comment_area:
                return False

            # 3. Focus and Type
            # We re-query or click to ensure focus. 
            # Note: The element might be 'detached' if we click and it re-renders. 
            # Safest is to click, wait a tiny bit, then type into the focused element or re-query.
            comment_area.click()
            self._random_delay(0.5, 1)
            
            # Re-query to be safe against DOM updates after click
            comment_area = self.page.query_selector(textarea_selector)
            if not comment_area:
                 comment_area = self.page.query_selector('textarea') # Fallback
            
            if comment_area:
                # Type slowly like a human
                for char in text:
                    comment_area.type(char, delay=random.randint(50, 150))
            else:
                logger.error("Textarea lost during interaction.")
                return False
            
            self._random_delay(1, 2)
            
            # 4. Submit
            # Try finding the specific 'Post' button first
            post_button_selectors = [
                'div[role="button"]:has-text("Post")',
                'button:has-text("Post")',
                'form button[type="submit"]',
                'div[class*="x1i10hfl"]:has-text("Post")' # Generic class sometimes used
            ]
            
            clicked_post = False
            for selector in post_button_selectors:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        clicked_post = True
                        break
                except:
                    continue
            
            if not clicked_post:
                logger.info("Could not find Post button, trying Enter key...")
                self.page.keyboard.press('Enter')
            
            self._random_delay(3, 5)
            
            # Verify if comment appeared (optional, tricky to do reliably without waiting too long)
            logger.info(f"Comment posted on {media_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error posting comment on {media_id}: {e}")
            return False

# Singleton removed — clients are now created per cycle in main.py
