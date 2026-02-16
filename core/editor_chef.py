
import random
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from config.settings import settings
from core.database import db
from core.models import SocialPlatform

from core.logger import logger

class SocialCopy(BaseModel):
    title: Optional[str] = Field(None, description="Title of the post, if applicable (e.g. for Dev.to).")
    body: str = Field(..., description="The main content of the post. MUST be in the platform's native style.")
    tags: List[str] = Field(default_factory=list, description="Relevant hashtags or tags.")
    reasoning: str = Field(..., description="AI reasoning for this specific copy.")

class EditorChef:
    def __init__(self):
        self.agent = self._create_transformation_agent()

    def _create_transformation_agent(self) -> Agent:
        # Load Persona
        persona_path = settings.BASE_DIR / "docs" / "persona" / "persona.md"
        try:
            with open(persona_path, "r", encoding="utf-8") as f:
                persona_content = f.read()
        except:
            persona_content = "You are a senior software engineer and tech influencer."

        instructions = f"""
        {persona_content}
        
        ## ROLE: THE EDITOR-IN-CHIEF
        Your task is to transform a raw content idea (news summary, personal insight, or project update) into a high-performance social media post.
        
        ## PLATFORM GUIDELINES
        
        ### Twitter/X:
        - Max 280 characters.
        - Punchy, direct, "no-bullshit".
        - Use abbreviations if they feel natural.
        - Max 1-2 relevant hashtags.
        
        ### Threads:
        - Conversational and engaging.
        - Slightly more relaxed than Twitter.
        - Focus on starting a discussion.
        
        ### Dev.to:
        - Needs a clear, technical Title.
        - Body should be more descriptive and structured (Markdown).
        - Include code snippets if the source content mentions specific logic.
        - Professional but casual tone.
        - Tags: Provide 1-4 plain text tags. Each tag MUST be a single word, alphanumeric, WITHOUT spaces or special characters (no '#').
        
        ## OUTPUT
        You MUST return a JSON matching the structured schema.
        """
        
        return Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Social Content Transformer",
            instructions=instructions,
            output_schema=SocialCopy,
            markdown=True
        )

    def is_business_day(self) -> bool:
        """Returns True if today is Monday to Friday."""
        return datetime.now().weekday() < 5  # 0=Mon, 4=Fri

    def can_publish(self, platform: str) -> bool:
        """Checks if limits allow publishing on this platform today."""
        if settings.BUSINESS_DAYS_ONLY and not self.is_business_day():
            logger.debug(f"Skipping {platform}: Not a business day.")
            return False

        # Check Daily/Weekly Limits
        try:
            # For Dev.to, we check weekly specific schedule
            if platform == "devto":
                today_name = datetime.now().strftime("%A")
                if today_name not in settings.DEVTO_SCHEDULE:
                    return False
                
                # Check if already posted today
                count_today = self._get_publication_count(platform, period="day")
                return count_today == 0
            
            # For Twitter/Threads, check daily limit
            limit = settings.PUBLISHING_LIMITS.get(platform, 10)
            count_today = self._get_publication_count(platform, period="day")
            
            return count_today < limit
        except Exception as e:
            logger.error(f"Error checking limits for {platform}: {e}")
            return False

    def _get_publication_count(self, platform: str, period: str = "day") -> int:
        """Queries the publications table for counts."""
        try:
            start_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            if period == "week":
                start_time = start_time - timedelta(days=start_time.weekday())
            
            res = db.client.table("publications") \
                .select("id", count="exact") \
                .eq("platform", platform) \
                .gte("created_at", start_time.isoformat()) \
                .execute()
            
            return res.count if res.count is not None else 0
        except Exception as e:
            logger.error(f"DB Count error: {e}")
            return 999  # Safety first: if DB fails, assume limit reached

    def select_content(self, platform: str) -> Optional[Dict]:
        """Selects a pending content idea based on the platform and current day."""
        today_name = datetime.now().strftime("%A")
        
        # Determine content type filter
        if today_name == settings.PROJECT_DAY:
            content_types = ["project_update"]
        else:
            # RNG for News vs Insights
            content_types = ["news"] if random.random() < settings.CONTENT_MIX["news"] else ["insight"]

        try:
            # Fetch pending ideas of selected types
            res = db.client.table("content_ideas") \
                .select("*") \
                .eq("status", "pending") \
                .in_("type", content_types) \
                .order("created_at", desc=True) \
                .limit(10) \
                .execute()
            
            if not res.data:
                # Fallback: if no ideas of chosen type, try ANY pending
                res = db.client.table("content_ideas") \
                    .select("*") \
                    .eq("status", "pending") \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()
            
            if res.data:
                return random.choice(res.data) # Add some randomness to selection
            return None
        except Exception as e:
            logger.error(f"Error selecting content: {e}")
            return None

    def transform_and_publish(self, client: Any):
        """Main entry point: selects, transforms, and executes publication."""
        platform = client.platform.value
        
        if not self.can_publish(platform):
            return

        # CHECK CAPABILITY: If client cannot post, skip immediately to save tokens and avoid loops
        if platform != "devto" and not hasattr(client, 'post_content'):
            logger.warning(f"[{platform}] Client does not support auto-publishing. Breaking loop.")
            return

        idea = self.select_content(platform)
        if not idea:
            logger.info(f"[{platform}] No pending content ideas found.")
            return

        logger.info(f"[{platform}] Transforming idea: {idea['title']}")
        
        prompt = f"""
        CONTENT TYPE: {idea['type']}
        SOURCE CONTENT:
        Title: {idea['title']}
        Summary: {idea['summary'] or ''}
        Original Trace: {idea['original_content']}
        
        PLATFORM: {platform}
        """

        try:
            response_obj = self.agent.run(prompt)
            copy: SocialCopy = response_obj.content
            
            logger.info(f"[{platform}] AI Copy Reasoning: {copy.reasoning}")
            
            if settings.dry_run:
                logger.info(f"[{platform}] DRY RUN: Subject: {copy.title} | Body: {copy.body[:100]}...")
                return

            # Execute Publication
            success = False
            post_id = None
            
            if platform == "devto":
                if hasattr(client, 'post_content'):
                    # Clean tags: alphanumeric, no spaces, lowercase
                    clean_tags = []
                    if copy.tags:
                        import re
                        for t in copy.tags:
                            clean_t = re.sub(r'[^a-zA-Z0-9]', '', t.lower())
                            if clean_t:
                                clean_tags.append(clean_t[:20]) # Limit length
                    
                    res = client.post_content(title=copy.title, body=copy.body, tags=clean_tags)
                    if res:
                        success = True
                        post_id = res.get("id")
            else:
                if hasattr(client, 'post_content'):
                    res = client.post_content(text=copy.body)
                    if res:
                        success = True
                        post_id = str(res) # Or specific ID

            if success:
                self._log_publication(idea['id'], platform, post_id, copy.body)
                # Mark as published
                db.client.table("content_ideas").update({"status": "published"}).eq("id", idea['id']).execute()
                logger.info(f"[{platform}] ✅ Published successfully!")
            
        except Exception as e:
            logger.error(f"Failed to publish to {platform}: {e}")

    def _log_publication(self, idea_id, platform, ext_id, text):
        try:
            data = {
                "content_idea_id": idea_id,
                "platform": platform,
                "ext_post_id": str(ext_id),
                "published_text": text
            }
            db.client.table("publications").insert(data).execute()
        except Exception as e:
            logger.error(f"Failed to log publication: {e}")
