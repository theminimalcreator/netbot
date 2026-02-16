"""
Playwright-based LinkedIn Client + API Auth
"""
import os
import time
import json
import random
import logging
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, Playwright
from core.browser_manager import BrowserManager
from core.interfaces import SocialNetworkClient
from core.models import SocialPost, SocialAuthor, SocialPlatform, SocialComment, SocialProfile
from config.settings import settings
from core.logger import NetBotLoggerAdapter

logger = NetBotLoggerAdapter(logging.getLogger('netbot'), {'network': 'LinkedIn'})

class LinkedInClient(SocialNetworkClient):
    """
    LinkedIn client:
    - API for auth validation and getting User URN
    - Playwright for Feed, Search, Like, Comment
    """
    
    TOKEN_FILE = "linkedin_token.json"
    STATE_FILE = "state_linkedin.json"
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        self.session_path = settings.BASE_DIR / "browser_state"
        self._is_logged_in = False
        
        # API Auth State
        self.access_token: Optional[str] = None
        self.person_urn: Optional[str] = None

    @property
    def platform(self) -> SocialPlatform:
        return SocialPlatform.LINKEDIN

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
            
            state_file = self.session_path / self.STATE_FILE
            if state_file.exists():
                logger.debug("Loading existing LinkedIn session...")
                self.context = self.browser.new_context(
                    storage_state=str(state_file),
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US'
                )
            else:
                logger.warning("No LinkedIn Playwright session found! (Run scripts/login_linkedin.py)")
                self.context = self.browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
            
            self.page = self.context.new_page()
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            return False

    def login(self) -> bool:
        """
        Validates API token and checks browser session.
        """
        # 1. API Token Check
        token_path = self.session_path / self.TOKEN_FILE
        if token_path.exists():
            try:
                with open(token_path, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    
                    # Optional: Check validity via API
                    # We use v2/userinfo because 'openid' scope doesn't give access to v2/me without r_liteprofile
                    hdrs = {"Authorization": f"Bearer {self.access_token}"}
                    resp = requests.get("https://api.linkedin.com/v2/userinfo", headers=hdrs, timeout=10)
                    
                    if resp.status_code == 200:
                        user_data = resp.json()
                        self.person_urn = f"urn:li:person:{user_data.get('sub')}" 
                        logger.info(f"LinkedIn API Auth Valid. User: {self.person_urn}")
                    else:
                        logger.warning(f"LinkedIn API Token validation failed: {resp.status_code}. Proceeding to browser check...")
                        # We continue to Playwright check. The API token might be for OpenID but we failed for some reason,
                        # or it's expired. But we want to try Browser Session.
            except Exception as e:
                logger.error(f"Error loading LinkedIn token: {e}")

        # 2. Browser Check
        if not self.page:
            if not self.start():
                return False

        try:
            logger.debug("Checking LinkedIn browser login status...")
            self.page.goto('https://www.linkedin.com/feed/', timeout=30000)
            self._random_delay(2, 4)
            
            # Check for feed element or profile nav
            # Using data-testid and data-view-name which are more stable than obfuscated classes
            has_nav = self.page.is_visible('[data-testid="primary-nav"]') or \
                      self.page.is_visible('[data-view-name="navigation-homepage"]') or \
                      self.page.is_visible('[data-view-name="feed-full-update"]')
            
            if has_nav:
                logger.info("LinkedIn: Browser Authenticated! (Nav bar found)")
                self._is_logged_in = True
                return True
            else:
                current_url = self.page.url
                logger.warning(f"LinkedIn: Login check failed. URL: {current_url}")
                if "login" in current_url or "guest" in current_url:
                    logger.warning("LinkedIn: Redirected to login/guest page.")
                else:
                    # Debug: Dump part of HTML to see what's there
                    content_sample = self.page.content()[:500]
                    logger.warning(f"LinkedIn: Page content sample: {content_sample}")
                    
                    # Save full HTML for debugging
                    try:
                        dump_path = settings.BASE_DIR / "debug_linkedin_dump.html"
                        with open(dump_path, "w", encoding="utf-8") as f:
                            f.write(self.page.content())
                        logger.warning(f"LinkedIn: Full HTML saved to {dump_path}")
                    except Exception as e:
                        logger.error(f"Failed to save debug dump: {e}")
                        
                return False

        except Exception as e:
            logger.error(f"LinkedIn login check failed: {e}")
            return False

    def stop(self):
        """Cleanup."""
        if self.context:
            try:
                self.session_path.mkdir(exist_ok=True, parents=True)
                # verify path is safe before saving
                state_file = self.session_path / self.STATE_FILE
                self.context.storage_state(path=str(state_file))
                self.context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            
        if self.browser:
            self.browser.close()
            
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    def get_feed_posts(self, limit: int = 10) -> List[SocialPost]:
        """Scrapes posts from the LinkedIn home feed."""
        if not self._is_logged_in:
             return []

        try:
            # --- STEP 1: Navigate to feed ---
            logger.info("[LINKEDIN] Loading feed...")
            if "feed" not in self.page.url:
                self.page.goto("https://www.linkedin.com/feed/", timeout=30000)
            
            self.page.wait_for_load_state("domcontentloaded")
            self._random_delay(3, 5)
            
            # Check initial post count
            initial_posts = len(self.page.query_selector_all('[data-view-name="feed-full-update"]'))
            logger.info(f"[LINKEDIN] Feed loaded. URL: {self.page.url} | Initial posts in DOM: {initial_posts}")

            # --- STEP 2: Scroll to load more posts ---
            # LinkedIn uses <main id="workspace"> as the scroll container (NOT window)
            import random
            max_scrolls = max(8, int(limit))
            if max_scrolls > 25: max_scrolls = 25

            # Detect scroll container
            has_workspace = self.page.evaluate("() => !!document.querySelector('#workspace')")
            if has_workspace:
                SCROLL_JS_HEIGHT = "() => { const el = document.querySelector('#workspace'); return el.scrollHeight; }"
                SCROLL_JS_DO = "() => { const el = document.querySelector('#workspace'); el.scrollTo(0, el.scrollHeight - 200); }"
                logger.info(f"[LINKEDIN] Scrolling #workspace (up to {max_scrolls}x)...")
            else:
                SCROLL_JS_HEIGHT = "() => document.body.scrollHeight"
                SCROLL_JS_DO = "() => window.scrollTo(0, document.body.scrollHeight - 200)"
                logger.info(f"[LINKEDIN] #workspace not found, using window scroll (up to {max_scrolls}x)...")
            
            prev_height = self.page.evaluate(SCROLL_JS_HEIGHT)
            stale_count = 0
            
            for i in range(max_scrolls):
                self.page.evaluate(SCROLL_JS_DO)
                
                # Wait for LinkedIn's AJAX to load new content
                loaded_new = False
                for wait_attempt in range(6):
                    self._random_delay(1, 1.5)
                    new_height = self.page.evaluate(SCROLL_JS_HEIGHT)
                    if new_height > prev_height:
                        loaded_new = True
                        break
                
                if loaded_new:
                    prev_height = new_height
                    stale_count = 0
                    if i % 3 == 0:
                        self._random_delay(2, 4)
                    else:
                        self._random_delay(1, 2)
                else:
                    stale_count += 1
                    if stale_count >= 3:
                        logger.info(f"[LINKEDIN] Scroll stopped — no new content for {stale_count} scrolls")
                        break
            
            final_posts = len(self.page.query_selector_all('[data-view-name="feed-full-update"]'))
            logger.info(f"[LINKEDIN] {final_posts} posts loaded after scrolling")

            # --- STEP 3: Parse posts ---
            post_selector = '[data-view-name="feed-full-update"]'
            posts_handles = self.page.query_selector_all(post_selector)
            
            if not posts_handles:
                # Fallback to legacy selector
                post_selector = 'div.feed-shared-update-v2'
                posts_handles = self.page.query_selector_all(post_selector)
                logger.info(f"[LINKEDIN] Using legacy selector, found {len(posts_handles)}")
            
            logger.info(f"[LINKEDIN] Parsing {min(len(posts_handles), limit * 3)} of {len(posts_handles)} post elements...")
            
            results = []
            for handle in posts_handles[:limit * 3]: # Scan more handles
                if len(results) >= limit: break
                
                post = self._parse_feed_post(handle)
                if post:
                    logger.info(f"   -> Candidate Found: {post.content[:60]}... (by {getattr(post.author, 'username', 'Unknown')})")
                    results.append(post)

            return results

        except Exception as e:
            logger.error(f"Error fetching feed: {e}")
            return []

    def search_posts(self, query: str, limit: int = 10) -> List[SocialPost]:
        """Searches LinkedIn by topic (keyword)."""
        if not self._is_logged_in: return []
        
        try:
            url = f"https://www.linkedin.com/search/results/content/?keywords={quote(query)}"
            logger.info(f"Searching LinkedIn: {url}", stage='A')
            self.page.goto(url, timeout=30000)
            self._random_delay(3, 5)

            # Scroll
            for _ in range(2):
                self.page.mouse.wheel(0, 600)
                self._random_delay(1, 2)
            
            # Use same parser as feed
            # Search results often have slightly different class but usually re-use feed-shared-update-v2
            # or `div.search-results-container div.artdeco-card`
             
            # Try core update selector first
            results = []
            # Search might share the feed update view or use a different one
            # We try multiple selectors
            handles = self.page.query_selector_all('[data-view-name="feed-full-update"]')
            if not handles:
                handles = self.page.query_selector_all('div.feed-shared-update-v2') 
            
            if not handles:
                 # Backup if layout is different in search
                 handles = self.page.query_selector_all('li.reusable-search__result-container')

            for handle in handles[:limit]:
                post = self._parse_feed_post(handle)
                if post:
                    logger.info(f"   -> Search Result: {post.content[:60]}... (by {getattr(post.author, 'username', 'Unknown')})")
                    results.append(post)
            
            return results

        except Exception as e:
            logger.error(f"Error searching {query}: {e}")
            return []

    def _parse_feed_post(self, container) -> Optional[SocialPost]:
        """Extracts SocialPost from a LinkedIn feed/search container."""
        try:
            # 1. Post ID (URN)
            import re
            import re as _re
            urn = container.get_attribute('data-urn')
            
            if not urn:
                # Strategy 1.5: Parent Traversal - decode Buffer byte array from data-view-tracking-scope
                # LinkedIn 2026 encodes URNs as numeric byte arrays inside a JSON Buffer
                try:
                    decoded_urn = container.evaluate("""(el) => {
                        let current = el.parentElement;
                        while (current && current !== document.body) {
                            const scope = current.getAttribute('data-view-tracking-scope');
                            if (scope) {
                                try {
                                    const parsed = JSON.parse(scope);
                                    for (const item of parsed) {
                                        // Check for Buffer-encoded URN
                                        if (item.breadcrumb && item.breadcrumb.content && item.breadcrumb.content.data) {
                                            const bytes = item.breadcrumb.content.data;
                                            const decoded = String.fromCharCode(...bytes);
                                            const match = decoded.match(/urn:li:activity:(\\d+)/);
                                            if (match) return match[0];
                                        }
                                        // Also check for isSponsored flag to skip ads
                                    }
                                } catch(e) {}
                            }
                            current = current.parentElement;
                        }
                        return null;
                    }""")
                    if decoded_urn:
                        urn = decoded_urn
                except Exception as e:
                    logger.debug(f"Buffer decode failed: {e}")

            if not urn:
                # Strategy 2: Check expected data-id which often contains the numerical ID
                data_id = container.get_attribute('data-id')
                if data_id and data_id.isdigit():
                    urn = f"urn:li:activity:{data_id}"
            
            if not urn:
                # Strategy 3: Check for any link to the post activity
                # Often shared-update-v2__content or similar has a link
                try:
                    link = container.query_selector('a[href*="urn:li:activity:"]')
                    if link:
                        href = link.get_attribute('href')
                        match = re.search(r'urn:li:activity:(\d+)', href)
                        if match:
                             urn = f"urn:li:activity:{match.group(1)}"
                except: pass

            if not urn:
                # Strategy 4: regex search in outerHTML (last resort)
                try:
                    html_content = container.evaluate("el => el.outerHTML")
                    urn_match = re.search(r'urn:li:activity:(\d+)', html_content)
                    if urn_match:
                        urn = f"urn:li:activity:{urn_match.group(1)}"
                except Exception as e:
                    logger.debug(f"Failed to regex URN: {e}")

            if not urn:
                try:
                    import time
                    debug_file = f"debug_linkedin_ad_or_error_{int(time.time())}.html"
                    # Only dump if user requested or debug level is high, but user asked for it.
                    # Use outerHTML to see the container attributes too
                    with open(debug_file, "w") as f:
                        f.write(container.evaluate("el => el.outerHTML"))
                    logger.debug(f"Dumped failed post to {debug_file}") # debug level to not spam ERROR
                except Exception as e:
                    logger.error(f"Failed to dump HTML: {e}")

            if not urn or "urn:li:activity" not in urn:
                 # Likely an ad or a promo without a standard activity URN
                 # Skip it to avoid errors downstream
                 return None

            post_id = urn.split(':')[-1]
            
            # 2. Author
            author_text = "Unknown"
            author_url = None
            
            # Modern: data-view-name="feed-actor-image" (Link) -> aria-label has name
            author_link = container.query_selector('[data-view-name="feed-actor-image"]')
            if author_link:
                href = author_link.get_attribute("href")
                if href: author_url = href.split('?')[0]
                
                aria = author_link.get_attribute("aria-label") 
                if aria:
                    # Handle: "View Name's profile", "Ver perfil de Name", or just the name
                    aria_clean = _re.sub(r"(View|Ver perfil de|'s profile|'s profile|profile|perfil)", "", aria, flags=_re.IGNORECASE).strip()
                    if aria_clean:
                        author_text = aria_clean
            
            if author_text == "Unknown" and author_link:
                # Try figure -> aria-label as fallback
                fig = author_link.query_selector("figure[aria-label]")
                if fig:
                    fig_label = fig.get_attribute("aria-label") or ""
                    fig_clean = _re.sub(r"(View|Ver perfil de|'s profile|'s profile|profile|perfil)", "", fig_label, flags=_re.IGNORECASE).strip()
                    if fig_clean:
                        author_text = fig_clean
            
            if author_text == "Unknown":
                # Legacy fallback
                actor_sel = container.query_selector('.update-components-actor__name, .update-components-actor__title, .feed-shared-actor__name, span[dir="ltr"] > span[aria-hidden="true"]') 
                if actor_sel:
                    author_text = actor_sel.inner_text().split('\n')[0].strip()

            # Username from URL — handle /in/username and /company/name
            username = author_text
            if author_url:
                if '/in/' in author_url:
                    username = author_url.split('/in/')[1].strip('/')
                elif '/company/' in author_url:
                    username = author_url.split('/company/')[1].strip('/')

            # 3. Content
            content = ""
            # Modern: data-view-name="feed-commentary"
            commentary = container.query_selector('[data-view-name="feed-commentary"]')
            if commentary:
                content = commentary.inner_text().strip()
            else:
                # Legacy
                text_el = container.query_selector('.feed-shared-text, .update-components-text')
                if text_el:
                    content = text_el.inner_text().strip()
            
            # 4. Metrics
            metrics = {"likes": 0, "comments": 0}
            
            # Modern Likes: data-view-name="feed-reaction-count"
            likes_node = container.query_selector('[data-view-name="feed-reaction-count"]')
            if likes_node:
                import re
                nums = re.findall(r'\d+', likes_node.inner_text().replace(',', '').replace('.', ''))
                if nums: metrics["likes"] = int(nums[0])
            
            # Modern Comments: data-view-name="feed-comment-count"
            comments_node = container.query_selector('[data-view-name="feed-comment-count"]')
            if comments_node:
                nums = re.findall(r'\d+', comments_node.inner_text().replace(',', '').replace('.', ''))
                if nums: metrics["comments"] = int(nums[0])

            if not content:
                # Try article title as fallback
                article_title = container.query_selector('.update-components-article__title')
                if article_title:
                    content = f"[Article] {article_title.inner_text()}"
            
            # 4. Metrics
            reactions = 0
            react_el = container.query_selector('.social-details-social-counts__reactions-count')
            if react_el:
                 try:
                     reactions = int(react_el.inner_text().strip().replace(',', '').replace('.', ''))
                 except: pass

            return SocialPost(
                id=post_id,
                platform=SocialPlatform.LINKEDIN,
                author=SocialAuthor(
                    username=username,
                    platform=SocialPlatform.LINKEDIN,
                    display_name=author_text,
                    profile_url=author_url
                ),
                content=content,
                url=f"https://www.linkedin.com/feed/update/{urn}/",
                metrics={"reaction_count": reactions},
                media_type="text" # Mostly text/mixed
            )

        except Exception as e:
            logger.warning(f"Parse error on post: {e}")
            return None

    def get_post_details(self, post_id: str) -> Optional[SocialPost]:
        """Navigates to post URL for details."""
        if not self._is_logged_in: return None
        
        url = f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/"
        try:
            self.page.goto(url, timeout=30000)
            self._random_delay(2, 3)
            
            # Reuses the main container parser on the single update
            container = self.page.query_selector('div.feed-shared-update-v2')
            if container:
                return self._parse_feed_post(container)
            return None
        except Exception as e:
            logger.error(f"Error fetching post details {post_id}: {e}")
            return None

    def like_post(self, post: Union[SocialPost, str]) -> bool:
        """Likes a post."""
        post_id = post.id if isinstance(post, SocialPost) else post
        
        if post_id == "unknown" or not post_id.isdigit():
             logger.error(f"Cannot like post with invalid ID: {post_id}")
             return False

        if settings.dry_run:
            logger.info(f"[DRY RUN] Would like LinkedIn post {post_id}")
            return True

        try:
            # Ensure we are on the post or can find it
            # If not on page, go to it
            current_url = self.page.url
            if post_id not in current_url:
                 self.page.goto(f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/", timeout=30000)
                 self._random_delay(2,3)

            # Find buttons
            # Selector: button with aria-label "Reaction button state: X" or data-view-name="reaction-button"
            
            # Search for the button within the update container
            btn = None
            try:
                # Modern 2026 selector
                # We prioritize buttons inside the specific update URN if possible
                btn = self.page.query_selector(f'[data-urn*="{post_id}"] button[data-view-name="reaction-button"]')
                if not btn:
                     btn = self.page.query_selector('button[data-view-name="reaction-button"]')
            except: pass

            if not btn: 
                # Fallback: by aria-label
                btn = self.page.query_selector('button[aria-label^="React Like"], button[aria-label^="Curtir"], button[aria-label*="Reaction button"]')
                
            if not btn:
                # Fallback: Generic react button class
                btn = self.page.query_selector('.reactions-react-button button')

            if btn:
                is_active = btn.get_attribute('aria-pressed') == 'true' or 'react-button--active' in (btn.get_attribute('class') or '')
                aria_label = btn.get_attribute('aria-label') or ""
                if "un-react" in aria_label.lower() or "descurtir" in aria_label.lower():
                    is_active = True
                
                if is_active:
                    logger.info(f"Post {post_id} already liked.")
                    return True
                
                btn.click()
                logger.info(f"Liked LinkedIn post {post_id}", stage='D')
                self._random_delay(1,2)
                return True
            
            logger.warning(f"Like button not found for {post_id}")
            return False

        except Exception as e:
            logger.error(f"Error liking {post_id}: {e}")
            return False

    def post_comment(self, post: Union[SocialPost, str], text: str) -> bool:
        """Comments on a post with full diagnostics."""
        post_id = post.id if isinstance(post, SocialPost) else post
        
        if post_id == "unknown" or not post_id.isdigit():
             logger.error(f"Cannot comment on post with invalid ID: {post_id}")
             return False

        if settings.dry_run:
            logger.info(f"[DRY RUN] Would comment on {post_id}: {text}")
            return True
        
        import time as _t
        import platform as _plat
        ts = int(_t.time())
        debug_prefix = f"debug_comment_{post_id}_{ts}"
            
        try:
            # Always navigate to the post page for a clean context
            post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{post_id}/"
            logger.info(f"Navigating to {post_url}")
            self.page.goto(post_url, timeout=30000)
            self.page.wait_for_load_state("domcontentloaded")
            self._random_delay(4, 6)
            
            # --- DIAGNOSTIC: Screenshot after page load ---
            try:
                self.page.screenshot(path=f"{debug_prefix}_1_loaded.png", full_page=False)
            except: pass
            
            # --- Step 1: Scroll down to the social bar / comment area ---
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self._random_delay(1, 2)
            
            # --- Step 2: Click the Comment button in the social bar ---
            comment_btn = None
            comment_selectors = [
                'button[data-view-name="feed-comment-button"]',
                'button[aria-label^="Comment"]',
                'button[aria-label^="Comentar"]',
            ]
            for sel in comment_selectors:
                try:
                    comment_btn = self.page.query_selector(sel)
                    if comment_btn:
                        logger.info(f"Step 2: Comment button found: {sel}")
                        break
                except: pass
            
            if comment_btn:
                comment_btn.scroll_into_view_if_needed()
                comment_btn.click()
                self._random_delay(2, 3)
            else:
                logger.warning("Step 2: Comment button NOT found — area may be open already")
            
            # --- Step 3: Click on the "Add a comment..." compact input to expand the full editor ---
            # LinkedIn shows a compact single-line input; clicking it expands the full editor with Submit
            compact_input = self.page.evaluate_handle("""() => {
                // Look for the compact comment input placeholder
                const placeholders = document.querySelectorAll(
                    '.comments-comment-box__form, [class*="comment-box"] .comments-comment-texteditor__content, [class*="comment-box"] [role="textbox"]'
                );
                for (const el of placeholders) return el;
                
                // Also try: any element with "Add a comment" text as placeholder
                const allInputs = document.querySelectorAll('[contenteditable="true"], [role="textbox"], input[placeholder*="comment" i], input[placeholder*="comentário" i]');
                for (const el of allInputs) return el;
                
                return null;
            }""").as_element()
            
            if compact_input:
                compact_input.scroll_into_view_if_needed()
                compact_input.click()
                logger.info("Step 3: Clicked compact comment input to expand editor")
                self._random_delay(2, 3)
            
            # --- DIAGNOSTIC: Screenshot after expanding editor ---
            try:
                self.page.screenshot(path=f"{debug_prefix}_2_editor_expanded.png", full_page=False)
            except: pass
            
            # --- Step 4: Find the comment editor (scoped) ---
            editor_el = self.page.evaluate_handle("""() => {
                // Strategy A: contenteditable inside comment-box containers
                const forms = document.querySelectorAll(
                    '.comments-comment-box, .comments-comment-texteditor, [class*="comment-box"], [class*="comment-texteditor"]'
                );
                for (const form of forms) {
                    const ed = form.querySelector('[contenteditable="true"], .ql-editor, [role="textbox"]');
                    if (ed) return ed;
                }
                // Strategy B: contenteditable with comment-related placeholder/aria-label
                const allEditable = document.querySelectorAll('[contenteditable="true"]');
                for (const el of allEditable) {
                    const ph = (el.getAttribute('data-placeholder') || '') + ' ' + 
                               (el.getAttribute('aria-placeholder') || '') + ' ' +
                               (el.getAttribute('aria-label') || '');
                    if (/comment|coment|add.*comment|adicionar/i.test(ph)) return el;
                }
                // Strategy C: role=textbox inside a comment section
                const textboxes = document.querySelectorAll('[role="textbox"]');
                for (const tb of textboxes) {
                    const parent = tb.closest('.comments-comment-box, .comments-comment-texteditor, [class*="comment"]');
                    if (parent) return tb;
                }
                return null;
            }""").as_element()
            
            if not editor_el:
                self._random_delay(2, 3)
                editor_el = self.page.query_selector('.comments-comment-box [contenteditable="true"], .comments-comment-texteditor [contenteditable="true"]')
            
            if not editor_el:
                logger.error("Step 4: Comment editor NOT found (scoped search)")
                try:
                    with open(f"{debug_prefix}_FAIL_no_editor.html", "w") as f:
                        f.write(self.page.content())
                    self.page.screenshot(path=f"{debug_prefix}_FAIL_no_editor.png", full_page=False)
                except: pass
                return False
            
            # Log what we found
            editor_info = editor_el.evaluate("""(el) => {
                return {
                    tag: el.tagName,
                    classes: el.className,
                    placeholder: el.getAttribute('data-placeholder') || el.getAttribute('aria-placeholder') || '',
                    role: el.getAttribute('role') || '',
                    parentClasses: el.parentElement ? el.parentElement.className : 'none'
                };
            }""")
            logger.info(f"Step 4: Editor found — tag={editor_info.get('tag')}, role={editor_info.get('role')}, placeholder='{editor_info.get('placeholder', '')[:50]}', parentClasses='{editor_info.get('parentClasses', '')[:80]}'")
            
            # --- Step 5: Type the comment ---
            editor_el.scroll_into_view_if_needed()
            editor_el.click()
            self._random_delay(0.5, 1)
            
            # Focus and clear
            editor_el.focus()
            select_all = "Meta+a" if _plat.system() == "Darwin" else "Control+a"
            self.page.keyboard.press(select_all)
            self.page.keyboard.press("Backspace")
            self._random_delay(0.3, 0.5)
            
            # Type character by character
            self.page.keyboard.type(text, delay=random.randint(30, 80))
            self._random_delay(1, 2)
            
            # Verify text was typed
            typed_text = editor_el.inner_text().strip()
            logger.info(f"Step 5: Typed {len(text)} chars. Editor contains {len(typed_text)} chars: '{typed_text[:60]}...'")
            
            if not typed_text:
                logger.error("Step 5: TYPING FAILED — editor is empty!")
                try:
                    self.page.screenshot(path=f"{debug_prefix}_FAIL_empty_editor.png", full_page=False)
                    with open(f"{debug_prefix}_FAIL_empty_editor.html", "w") as f:
                        f.write(self.page.content())
                except: pass
                return False
            
            # --- DIAGNOSTIC: Screenshot after typing ---
            try:
                self.page.screenshot(path=f"{debug_prefix}_3_typed.png", full_page=False)
            except: pass
            
            # --- Step 6: Find and click Submit button ---
            # Use JavaScript to find the submit button inside comment box with multiple strategies
            submit_btn = self.page.evaluate_handle("""() => {
                // Strategy A: Standard class-based selectors
                const classSelectors = [
                    'button.comments-comment-box__submit-button',
                    'button[data-view-name="comments-comment-box-submit-button"]',
                ];
                for (const sel of classSelectors) {
                    const btn = document.querySelector(sel);
                    if (btn && !btn.disabled) return btn;
                }
                
                // Strategy B: Find buttons inside comment box containers by aria-label
                const commentBoxes = document.querySelectorAll(
                    '.comments-comment-box, .comments-comment-texteditor, [class*="comment-box"], [class*="comment-texteditor"]'
                );
                for (const box of commentBoxes) {
                    const buttons = box.querySelectorAll('button');
                    for (const btn of buttons) {
                        const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                        const text = (btn.textContent || '').toLowerCase().trim();
                        if (/post|publicar|submit|enviar|comment|comentar/i.test(label + ' ' + text)) {
                            if (!btn.disabled) return btn;
                        }
                    }
                }
                
                // Strategy C: Any button with post/submit in aria-label (broader search)
                const allButtons = document.querySelectorAll('button[aria-label]');
                for (const btn of allButtons) {
                    const label = btn.getAttribute('aria-label').toLowerCase();
                    if (/post comment|publicar coment|submit comment/i.test(label)) {
                        if (!btn.disabled) return btn;
                    }
                }
                
                // Strategy D: Look for a submit-type button near the editor
                const editor = document.querySelector('[contenteditable="true"]');
                if (editor) {
                    const form = editor.closest('form, .comments-comment-box, [class*="comment-box"]');
                    if (form) {
                        const btn = form.querySelector('button[type="submit"], button:not([aria-label*="emoji"]):not([aria-label*="photo"]):not([aria-label*="image"])');
                        if (btn && !btn.disabled) return btn;
                    }
                }
                
                return null;
            }""").as_element()
            
            submit_method = "none"
            if submit_btn:
                submit_btn.scroll_into_view_if_needed()
                submit_btn.click()
                submit_method = "button_click"
                logger.info("Step 6: Submit button FOUND and clicked")
            else:
                # Log all buttons on page for debugging
                all_btns_info = self.page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    const info = [];
                    btns.forEach((btn, i) => {
                        const label = btn.getAttribute('aria-label') || '';
                        const text = (btn.textContent || '').trim().substring(0, 30);
                        const classes = btn.className.substring(0, 60);
                        const disabled = btn.disabled;
                        if (label || text) info.push({i, label, text, classes, disabled});
                    });
                    return info;
                }""")
                logger.warning(f"Step 6: Submit button NOT found. All buttons on page: {all_btns_info}")
                
                # Fallback: Tab to the submit button and press Enter
                logger.info("Step 6: Trying Tab+Enter to reach submit button...")
                self.page.keyboard.press("Tab")
                self._random_delay(0.3, 0.5)
                self.page.keyboard.press("Enter")
                submit_method = "tab_enter"
            
            self._random_delay(5, 8)
            
            # --- DIAGNOSTIC: Screenshot after submit ---
            try:
                self.page.screenshot(path=f"{debug_prefix}_4_submitted.png", full_page=False)
            except: pass
            
            # --- Step 7: Verify the comment was actually posted ---
            # CRITICAL: We need to check that the comment appears OUTSIDE the editor
            # First, read current editor text (if still present)
            editor_remaining = ""
            try:
                ed_check = self.page.query_selector('.comments-comment-box [contenteditable="true"], .comments-comment-texteditor [contenteditable="true"], [role="textbox"]')
                if ed_check:
                    editor_remaining = ed_check.inner_text().strip()
            except: pass
            
            verify_snippet = text[:40]
            
            # If text is still in the editor → submission failed
            if editor_remaining and verify_snippet in editor_remaining:
                logger.error(f"Step 7: SUBMIT FAILED — text still in editor! Submit method was: {submit_method}")
                try:
                    with open(f"{debug_prefix}_FAIL_not_submitted.html", "w") as f:
                        f.write(self.page.content())
                    self.page.screenshot(path=f"{debug_prefix}_5_not_submitted.png", full_page=False)
                except: pass
                return False
            
            # Check if snippet appears in comments section (not editor)
            is_verified = self.page.evaluate("""(snippet) => {
                // Look in comment items specifically
                const commentEls = document.querySelectorAll(
                    '.comments-comment-item, .comments-comment-entity, [class*="comment-item"], [class*="comment-entity"], .comments-comments-list'
                );
                for (const c of commentEls) {
                    if (c.innerText.includes(snippet)) return true;
                }
                return false;
            }""", verify_snippet)
            
            if is_verified:
                logger.info(f"✅ Comment VERIFIED on post {post_id}", stage='D')
                return True
            
            # Retry after more time
            self._random_delay(3, 5)
            body_text = self.page.evaluate("() => document.body.innerText")
            if verify_snippet in body_text:
                # Make sure it's not just in the editor
                if not editor_remaining or verify_snippet not in editor_remaining:
                    logger.info(f"✅ Comment VERIFIED on post {post_id} (retry)", stage='D')
                    return True
            
            # NOT verified
            logger.warning(f"⚠️ Comment on {post_id} NOT VERIFIED — submit_method={submit_method}")
            try:
                with open(f"{debug_prefix}_FAIL_unverified.html", "w") as f:
                    f.write(self.page.content())
                self.page.screenshot(path=f"{debug_prefix}_5_unverified.png", full_page=False)
            except: pass
            return False

        except Exception as e:
            logger.error(f"Error commenting {post_id}: {e}")
            try:
                self.page.screenshot(path=f"{debug_prefix}_EXCEPTION.png", full_page=False)
                with open(f"{debug_prefix}_EXCEPTION.html", "w") as f:
                    f.write(self.page.content())
            except: pass
            return False
            
    def get_profile_data(self, username: str) -> Optional[SocialProfile]:
        """Scrapes detailed profile data."""
        if not self._is_logged_in: return None
        try:
            url = f"https://www.linkedin.com/in/{username}/"
            self.page.goto(url, timeout=30000)
            self._random_delay(2,3)
            
            # Bio / Headline
            headline = ""
            hl_el = self.page.query_selector('.text-body-medium')
            if hl_el:
                headline = hl_el.inner_text().strip()
                
            # About
            about = ""
            about_el = self.page.query_selector('#about ~ .display-flex .inline-show-more-text')
            if about_el:
                 about = about_el.inner_text().strip()
            
            return SocialProfile(
                username=username,
                platform=SocialPlatform.LINKEDIN,
                bio=headline + "\n" + about,
                profile_url=url
            )
        except Exception as e:
            logger.error(f"Error fetching profile {username}: {e}")
            return None
