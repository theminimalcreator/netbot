"""
Playwright-based Twitter/X Client with Tweepy API support for interactions.
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

import tweepy
from config.settings import settings

logger = logging.getLogger(__name__)

class TwitterClient(SocialNetworkClient):
    """
    Twitter/X client using Playwright for discovery and Tweepy API for interactions.
    """
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.session_path = Path("browser_state")
        self._is_logged_in = False

        # Initialize Tweepy Client
        self.api_client = None
        if settings.TWITTER_API_KEY and settings.TWITTER_API_SECRET and \
           settings.TWITTER_ACCESS_TOKEN and settings.TWITTER_ACCESS_TOKEN_SECRET:
            try:
                self.api_client = tweepy.Client(
                    consumer_key=settings.TWITTER_API_KEY,
                    consumer_secret=settings.TWITTER_API_SECRET,
                    access_token=settings.TWITTER_ACCESS_TOKEN,
                    access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET
                )
                logger.info("Twitter API Client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Twitter API Client: {e}")
        else:
            logger.warning("Twitter API keys missing. Fallback to Playwright for all actions (expect limited functionality or bans).")
    
    @property
    def platform(self) -> SocialPlatform:
        return SocialPlatform.TWITTER
    
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
            
            state_file = self.session_path / "state_twitter.json"
            if state_file.exists():
                logger.debug("Loading existing Twitter session...")
                self.context = self.browser.new_context(
                    storage_state=str(state_file),
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/Sao_Paulo'
                )
            else:
                logger.warning("No Twitter session found!")
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
            logger.debug("Checking Twitter login status...")
            self.page.goto('https://x.com/home', timeout=30000)
            self._random_delay(2, 4)
            
            try:
                # Check for Home or Post button
                self.page.wait_for_selector('div[aria-label="Home"], a[aria-label="Home"]', timeout=5000)
                logger.debug("Twitter: Already logged in!")
                self._is_logged_in = True
                return True
            except:
                logger.warning("Twitter: Not logged in. Please run scripts/login_twitter.py")
                return False
                
        except Exception as e:
            logger.error(f"Twitter login check failed: {e}")
            return False

    def stop(self):
        """Cleanup."""
        if self.context:
            try:
                self.session_path.mkdir(exist_ok=True, parents=True)
                # self.context.storage_state(path=str(self.session_path / "state_twitter.json"))
                self.context.close()
            except:
                pass
        if self.browser:
            try:
                self.browser.close()
            except: pass

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    def get_post_details(self, post_id: str) -> Optional[SocialPost]:
        """Fetches tweet details."""
        if not self._is_logged_in:
            return None
            
        try:
            url = f"https://x.com/i/status/{post_id}"
            self.page.goto(url, timeout=30000)
            self._random_delay(2, 3)
            
            # Selectors (using data-testid is best for Twitter)
            # Article: article[data-testid="tweet"]
            
            tweet_article = self.page.query_selector('article[data-testid="tweet"]')
            if not tweet_article:
                return None
            
            # Author
            username = "unknown"
            user_links = tweet_article.query_selector_all('a[href*="/"]')
            for link in user_links:
                href = link.get_attribute('href')
                if href and href.count('/') == 1 and not 'status' in href:
                     username = href.strip('/')
                     break
            
            # Content
            content = ""
            text_div = tweet_article.query_selector('div[data-testid="tweetText"]')
            if text_div:
                content = text_div.inner_text()
            
            # Media
            media_urls = []
            imgs = tweet_article.query_selector_all('img[src*="pbs.twimg.com/media"]')
            for img in imgs:
                src = img.get_attribute('src')
                if src:
                    media_urls.append(src)
            
            return SocialPost(
                id=post_id,
                platform=self.platform,
                author=SocialAuthor(username=username, platform=self.platform),
                content=content,
                url=url,
                media_urls=media_urls,
                media_type="image" if media_urls else "text"
            )
            
        except Exception as e:
            logger.error(f"Error fetching tweet {post_id}: {e}")
            return None

    def like_post(self, post: Union[SocialPost, str]) -> bool:
        """Likes a tweet using API if available, else Playwright."""
        # Get ID safely
        post_id = getattr(post, "id", post) if hasattr(post, "id") else str(post)

        if self.api_client:
            try:
                logger.info(f"[Twitter API] Liking tweet {post_id}...")
                response = self.api_client.like(tweet_id=post_id)
                # response.data['liked'] should be True
                if response.data and response.data.get('liked'):
                    logger.info(f"Liked tweet {post_id}")
                    return True
                else:
                    logger.warning(f"API like response unexpected: {response}")
                    return False
            except Exception as e:
                logger.error(f"Twitter API Like failed: {e}")
                # Fallback to Playwright if desired, but usually API failure means auth/rate-limit
                # and browser fallback might be risky. Let's try browser fallback only if explicitly enabled?
                # For now, let's fall back since the user might be migrating.
                pass

        # Fallback to Playwright
        if not self.page or not self.context:
            if not self.start():
                return False
        
        try:
            url = f"https://x.com/i/status/{post_id}"
            if self.page.url != url:
                self.page.goto(url, timeout=30000)
            
            like_btn_sel = 'button[data-testid="like"]'
            unlike_btn_sel = 'button[data-testid="unlike"]'
            
            if self.page.is_visible(unlike_btn_sel):
                logger.debug(f"Already liked tweet {post_id}")
                return True
                
            if self.page.is_visible(like_btn_sel):
                self.page.click(like_btn_sel)
                try:
                    self.page.wait_for_selector(unlike_btn_sel, timeout=5000)
                    logger.info(f"Liked tweet {post_id} (Browser)")
                    return True
                except:
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error liking tweet {post_id}: {e}")
            return False

    def post_comment(self, post: Union[SocialPost, str], text: str) -> bool:
        """Replies to a tweet using API if available, else Playwright."""
        # Get ID safely
        post_id = getattr(post, "id", post) if hasattr(post, "id") else str(post)

        if self.api_client:
            try:
                logger.info(f"[Twitter API] Replying to {post_id}: {text}")
                response = self.api_client.create_tweet(text=text, in_reply_to_tweet_id=post_id)
                if response.data and response.data.get('id'):
                    logger.info(f"Replied to {post_id} (API ID: {response.data['id']})")
                    return True
                else:
                    logger.warning(f"API reply response unexpected: {response}")
                    return False
            except Exception as e:
                logger.error(f"Twitter API Reply failed: {e}")
                pass

        # Fallback to Playwright
        if not self.page or not self.context:
             if not self.start():
                 return False

        try:
            url = f"https://x.com/i/status/{post_id}"
            if self.page.url != url:
                self.page.goto(url, timeout=30000)
            
            reply_trigger = 'button[data-testid="reply"]'
            if self.page.is_visible(reply_trigger):
                self.page.click(reply_trigger)
                self.page.wait_for_timeout(1000)
            
            editor_sel = 'div[data-testid="tweetTextarea_0"]'
            self.page.wait_for_selector(editor_sel, timeout=5000)
            self.page.click(editor_sel)
            self.page.keyboard.type(text)
            
            send_btn_sel = 'button[data-testid="tweetButton"]'
            self.page.wait_for_selector(send_btn_sel, timeout=5000)
            
            if self.page.is_disabled(send_btn_sel):
                logger.warning("Reply button is disabled")
                return False
                
            self.page.click(send_btn_sel)
            self.page.wait_for_selector(send_btn_sel, state="hidden", timeout=10000)
            logger.info(f"Replied to {post_id} (Browser)")
            return True

        except Exception as e:
            logger.error(f"Error replying to {post_id}: {e}")
            return False

    def post_content(self, text: str) -> Optional[str]:
        """Posts a new tweet using API if available, else Playwright."""
        if self.api_client:
            try:
                logger.info(f"[Twitter API] Posting tweet: {text}")
                response = self.api_client.create_tweet(text=text)
                if response.data and response.data.get('id'):
                    logger.info(f"Posted tweet (API ID: {response.data['id']})")
                    return "success"
                else:
                    logger.warning(f"API post response unexpected: {response}")
                    return None
            except Exception as e:
                logger.error(f"Twitter API Post failed: {e}")
                pass

        # Fallback to Playwright
        if not self.page or not self.context:
             if not self.start():
                 return None

        try:
            logger.info("[Twitter] Posting new content...")
            self.page.goto("https://x.com/home", timeout=30000)
            self._random_delay(2, 4)
            
            editor_sel = 'div[data-testid="tweetTextarea_0"]'
            if not self.page.is_visible(editor_sel):
                post_btn = 'a[data-testid="SideNav_NewTweet_Button"]'
                self.page.wait_for_selector(post_btn, timeout=5000)
                self.page.click(post_btn)
                self.page.wait_for_selector(editor_sel, timeout=5000)

            self.page.click(editor_sel)
            self.page.keyboard.type(text, delay=20)
            self._random_delay(1, 2)

            send_btn_sel = 'button[data-testid="tweetButtonInline"], button[data-testid="tweetButton"]'
            try:
                self.page.wait_for_function(
                    f"""() => {{
                        const btn = document.querySelector('{send_btn_sel}');
                        return btn && !btn.disabled && btn.getAttribute('aria-disabled') !== 'true';
                    }}""",
                    timeout=10000
                )
            except Exception as e:
                logger.warning(f"[Twitter] Send button remained disabled: {e}")
                return None

            try:
                self.page.evaluate(f"document.querySelector('{send_btn_sel}').click()")
            except:
                self.page.click(send_btn_sel, force=True)
            
            try:
                self.page.wait_for_selector('div[data-testid="toast"]', timeout=5000)
                return "success"
            except:
                pass

            self.page.wait_for_function(
                f"""() => {{
                    const editor = document.querySelector('{editor_sel}');
                    if (!editor) return true;
                    const style = window.getComputedStyle(editor);
                    if (style.display === 'none' || style.visibility === 'hidden') return true;
                    return editor.innerText.trim().length === 0;
                }}""",
                timeout=10000
            )
            return "success"

        except Exception as e:
            logger.error(f"[Twitter] Error posting new content: {e}")
            return None

    def get_profile_data(self, username: str) -> Optional[SocialProfile]:
        """Fetches X profile data."""
        # For now, we don't have a reliable way to scrape bio without risking detection on X.
        return None

    def get_user_latest_posts(self, username: str, limit: int = 5) -> List[SocialPost]:
        """Fetches latest posts from a user's profile."""
        if not self._is_logged_in: return []
        
        try:
            url = f"https://x.com/{username}"
            logger.info(f"Visiting profile: {url}")
            self.page.goto(url, timeout=30000)
            self._random_delay(2, 4)
            
            for _ in range(2):
                self.page.mouse.wheel(0, 500)
                self._random_delay(0.5, 1)
            
            tweets = self.page.query_selector_all('article[data-testid="tweet"]')
            results = []
            
            for tweet in tweets[:limit]:
                link = tweet.query_selector('a[href*="/status/"]')
                if link:
                    href = link.get_attribute('href')
                    post_id = None
                    if "/status/" in href:
                        post_id = href.split('/status/')[-1].split('/')[0]
                    
                    if post_id:
                        text_div = tweet.query_selector('div[data-testid="tweetText"]')
                        content = text_div.inner_text() if text_div else ""
                        
                        logger.info(f"   Found tweet {post_id}: {content[:30]}...")
                        
                        results.append(SocialPost(
                            id=post_id,
                            platform=self.platform,
                            author=SocialAuthor(username=username, platform=self.platform),
                            content=content,
                            url=f"https://x.com{href}" if href.startswith('/') else href,
                            media_type="text" 
                        ))
            
            return results
        except Exception as e:
            logger.error(f"Error fetching posts for {username}: {e}")
            return []

    def search_posts(self, query: str, limit: int = 5) -> List[SocialPost]:
        """Searches for posts by hashtag/query."""
        if not self._is_logged_in: return []
        
        try:
            url = f"https://x.com/search?q=%23{query}&src=typed_query&f=live"
            logger.info(f"Searching: {url}")
            self.page.goto(url, timeout=30000)
            self._random_delay(2, 4)
            
            tweets = self.page.query_selector_all('article[data-testid="tweet"]')
            results = []
            
            for tweet in tweets[:limit]:
                 link = tweet.query_selector('a[href*="/status/"]')
                 if link:
                    href = link.get_attribute('href')
                    parts = href.split('/')
                    if len(parts) >= 4 and parts[2] == 'status':
                        username = parts[1]
                        post_id = parts[3]
                        
                        text_div = tweet.query_selector('div[data-testid="tweetText"]')
                        content = text_div.inner_text() if text_div else ""
                        
                        results.append(SocialPost(
                            id=post_id,
                            platform=self.platform,
                            author=SocialAuthor(username=username, platform=self.platform),
                            content=content,
                            url=f"https://x.com{href}",
                            media_type="text"
                        ))
            return results
        except Exception as e:
            logger.error(f"Error searching {query}: {e}")
            return []
