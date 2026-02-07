"""
Playwright-based Instagram Client

Uses a real browser for all Instagram operations:
- Session management with persistent context
- Post extraction (caption, media, comments)
- Comment posting
- Profile/hashtag browsing for discovery
"""
import os
import json
import logging
import random
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import unquote

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright

from config.settings import settings

logger = logging.getLogger(__name__)


class PlaywrightInstagramClient:
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
    
    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Human-like random delay."""
        time.sleep(random.uniform(min_sec, max_sec))
    
    def start(self) -> bool:
        """Initialize browser and load session."""
        try:
            self.playwright = sync_playwright().start()
            
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
                    locale='pt-BR',
                    timezone_id='America/Sao_Paulo'
                )
            else:
                logger.info("Creating new browser context...")
                self.context = self.browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='pt-BR',
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
                    'svg[aria-label="Home"], svg[aria-label="Página inicial"], a[href="/direct/inbox/"]',
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
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=False,  # User needs to see this
                args=['--disable-blink-features=AutomationControlled']
            )
            
            self.context = self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='pt-BR',
                timezone_id='America/Sao_Paulo'
            )
            
            self.page = self.context.new_page()
            self.page.goto('https://www.instagram.com/accounts/login/')
            
            logger.info("Please login in the browser window...")
            
            # Wait for successful login (up to 5 minutes)
            self.page.wait_for_selector(
                'svg[aria-label="Home"], svg[aria-label="Página inicial"], a[href="/direct/inbox/"]',
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
        if self.playwright:
            self.playwright.stop()
        
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
            self._random_delay(1, 2)
            
            # Extract username from the post header
            username = ""
            username_selectors = [
                'header a[role="link"]',
                'header a[href*="/"]',
                'a[href*="/"] span',
                'article header a'
            ]
            for sel in username_selectors:
                try:
                    el = self.page.query_selector(sel)
                    if el:
                        href = el.get_attribute('href')
                        if href and '/' in href:
                            username = href.strip('/').split('/')[-1]
                            if username and username not in ['p', 'explore', 'reels']:
                                break
                except:
                    continue
            
            logger.info(f"Extracted username: {username}")
            
            # Extract caption - try multiple approaches
            caption = ""
            caption_selectors = [
                'h1',
                'article h1',
                'div[role="button"] span',
                'article span[dir="auto"]',
                'ul li span[dir="auto"]',
                'article div > span'
            ]
            for sel in caption_selectors:
                try:
                    el = self.page.query_selector(sel)
                    if el:
                        text = el.inner_text()
                        if text and len(text) > 10:  # Ignore very short texts
                            caption = text
                            break
                except:
                    continue
            
            # If still no caption, try getting all visible text from the post area
            if not caption:
                try:
                    # Get text from the right side panel (where caption usually is)
                    panel = self.page.query_selector('article section, article > div > div:nth-child(2)')
                    if panel:
                        caption = panel.inner_text()[:500]  # Limit to 500 chars
                except:
                    pass
            
            logger.info(f"Extracted caption ({len(caption)} chars): {caption[:100]}...")
            
            # Extract image URL
            image_url = None
            img_selectors = [
                'article img[src*="instagram"]',
                'article img[src*="cdninstagram"]',
                'img[src*="scontent"]',
                'article img',
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
            
            logger.info(f"Extracted image URL: {image_url[:50] if image_url else 'None'}...")
            
            # Extract comments
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
    
    def get_media_info(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Gets full details of a media by its code."""
        return self._get_post_data(media_id)
    
    def get_media_comments(self, media_id: str, amount: int = 5) -> List[Dict[str, str]]:
        """Fetches comments from a media."""
        # Navigate to post first
        self.page.goto(f'https://www.instagram.com/p/{media_id}/', timeout=30000)
        self._random_delay(1, 2)
        return self._get_post_comments(amount)
    
    def like_post(self, media_id: str) -> bool:
        """Likes a post."""
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
                'svg[aria-label="Curtir"]',
                'svg[aria-label="Gefällt mir"]',
                # Unliked state usually has these labels. Liked has "Unlike" / "Descurtir"
            ]
            
            # If we find an "Unlike" or "Descurtir" button, it's already liked
            already_liked_selectors = [
                'svg[aria-label="Unlike"]',
                'svg[aria-label="Descurtir"]'
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
    
    def post_comment(self, media_id: str, text: str) -> bool:
        """Posts a comment on a media."""
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
                comment_icon_selector = 'svg[aria-label="Comment"], svg[aria-label="Comentar"], svg[aria-label="Responder"], span[class*="_aamx"]'
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
            textarea_selector = 'textarea[aria-label*="omment"], textarea[aria-label*="comentário"], textarea[placeholder*="omment"], textarea[placeholder*="comentário"], form textarea'
            
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
                'div[role="button"]:has-text("Publicar")', 
                'button:has-text("Post")',
                'button:has-text("Publicar")',
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


# Singleton instance
client = PlaywrightInstagramClient()
