"""
Layer 2: Context Builder — Pure Python Aggregator

No LLM call here. Assembles all context needed for the Ghostwriter:
- RAG (past interactions from KnowledgeBase)
- Profile Dossier (via ProfileAnalyzer — this IS an LLM call, but owned by ProfileAnalyzer)
- Engagement signals (metrics-based)
- Comment context
- Platform-specific style guide
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from core.models import SocialPost, SocialPlatform
from core.knowledge_base import NetBotKnowledgeBase
from core.profile_analyzer import ProfileAnalyzer, ProfileDossier
from core.chains.judge import JudgeVerdict
from core.logger import logger, NetBotLoggerAdapter


class EngagementContext(BaseModel):
    """All context needed by the Ghostwriter to generate a comment."""

    # Post data
    post_id: str
    platform: SocialPlatform
    author_username: str
    content: str
    media_type: str
    media_urls: List[str] = Field(default_factory=list)

    # From Judge (Layer 1)
    category: str
    language: str

    # Engagement signals
    engagement_signal: str  # "Low", "Medium", "High"
    strategy: str  # Hot take instruction
    reply_count: int = 0
    like_count: int = 0

    # Dossier (from ProfileAnalyzer)
    dossier_block: str = ""

    # RAG (past interactions)
    rag_block: str = ""

    # Comments context
    comments_block: str = ""

    # Platform style
    char_limit: str = ""
    style_guide: str = ""


class ContextBuilder:
    """
    Pure Python layer that aggregates context from multiple sources.
    The only LLM call here is the ProfileAnalyzer (optional, for high-value targets).
    """

    def __init__(self, knowledge_base: NetBotKnowledgeBase, profile_analyzer: ProfileAnalyzer):
        self.knowledge_base = knowledge_base
        self.profile_analyzer = profile_analyzer
        self.logger = NetBotLoggerAdapter(logger, {'stage': 'C', 'status_code': 'CONTEXT'})

    def build(self, post: SocialPost, verdict: JudgeVerdict, client=None) -> EngagementContext:
        """
        Assembles all context needed for the Ghostwriter.

        Args:
            post: The social media post.
            verdict: The Judge's verdict (category, language).
            client: Optional platform client (to fetch profile data for dossier).
        """
        self.logger.info(f"🔧 Building context for post {post.id}...")

        # 1. Engagement signals
        metrics = getattr(post, 'metrics', {})
        reply_count = metrics.get('reply_count', 0)
        like_count = metrics.get('like_count', 0)

        engagement_signal = "Low"
        strategy = "Kickstart the conversation. Be provocative but polite."

        if reply_count > 10:
            engagement_signal = "High"
            strategy = "Join the flow. Reply to a specific point from existing comments (if valid)."
        elif reply_count > 0:
            engagement_signal = "Medium"
            strategy = "Add a constructive perspective to the existing discussion."

        # 2. Comments context
        comments_block = ""
        if post.comments:
            formatted = "\n".join([f"- @{c.author.username}: {c.text}" for c in post.comments])
            comments_block = f"Recent Comments:\n{formatted}"

        # 3. RAG: Search for consistency
        rag_block = ""
        try:
            past_takes = self.knowledge_base.search_similar_takes(post.content, limit=2)
            if past_takes:
                rag_block = "\n".join([f"- {take}" for take in past_takes])
        except Exception as e:
            self.logger.warning(f"RAG search failed: {e}")

        # 4. Profile Dossier (optional LLM call via ProfileAnalyzer)
        dossier_block = ""
        if client and hasattr(client, 'get_profile_data') and callable(client.get_profile_data):
            try:
                self.logger.debug(f"Gathering dossier for @{post.author.username}...")
                profile_data = client.get_profile_data(post.author.username)
                if profile_data:
                    dossier = self.profile_analyzer.analyze_profile(profile_data)
                    if dossier:
                        dossier_block = self._format_dossier(post.author.username, dossier)
            except Exception as e:
                self.logger.warning(f"Dossier generation failed: {e}")

        # 5. Platform style guide
        char_limit, style_guide = self._get_platform_style(post.platform)

        context = EngagementContext(
            post_id=post.id,
            platform=post.platform,
            author_username=post.author.username,
            content=post.content,
            media_type=post.media_type,
            media_urls=post.media_urls,
            category=verdict.category.value,
            language=verdict.language,
            engagement_signal=engagement_signal,
            strategy=strategy,
            reply_count=reply_count,
            like_count=like_count,
            dossier_block=dossier_block,
            rag_block=rag_block,
            comments_block=comments_block,
            char_limit=char_limit,
            style_guide=style_guide
        )

        self.logger.info(
            f"📦 Context built: Signal={engagement_signal} | "
            f"RAG={'Yes' if rag_block else 'No'} | "
            f"Dossier={'Yes' if dossier_block else 'No'}"
        )
        return context

    def _format_dossier(self, username: str, dossier: ProfileDossier) -> str:
        hype_alert = "🚨 YES (HYPE SELLER DETECTED) 🚨" if dossier.is_hype_seller else "No"
        return f"""- Summary: {dossier.summary}
- Job Title: {dossier.job_title}
- Technical Level: {dossier.technical_level.value}
- Hype Seller: {hype_alert}
- Interests: {', '.join(dossier.interests)}
- Tone Preference: {dossier.tone_preference}
- INTERACTION GUIDELINES: {dossier.interaction_guidelines}

IMPORTANT: Adapt your response to match this person's level and tone."""

    def _get_platform_style(self, platform: SocialPlatform) -> tuple[str, str]:
        styles = {
            SocialPlatform.TWITTER: (
                "280 characters",
                "Use abbreviations if needed, no hashtags unless relevant, casual but professional."
            ),
            SocialPlatform.THREADS: (
                "proportional to the post length",
                "Conversational, threading-friendly, casual."
            ),
            SocialPlatform.LINKEDIN: (
                "proportional to the post length",
                "Professional, constructive, slightly more formal."
            ),
            SocialPlatform.DEVTO: (
                "proportional to the post length",
                "Technical, in-depth, explanatory, code-friendly, professional."
            ),
            SocialPlatform.INSTAGRAM: (
                "proportional to the post length",
                "Casual, helpful, Instagram-native."
            ),
        }
        return styles.get(platform, ("proportional to the post length", "Casual, helpful."))
