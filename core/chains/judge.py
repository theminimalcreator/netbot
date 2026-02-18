"""
Layer 1: The Judge — Semantic Filter

Lightweight LLM call that decides if a post is worth engaging with.
Uses minimal prompt (no persona, no RAG) to save tokens on rejected posts.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from core.logger import logger, NetBotLoggerAdapter
from core.models import SocialPost


class PostCategory(str, Enum):
    TECHNICAL = "Technical"
    CAREER = "Career"
    NETWORKING = "Networking"
    OPINION = "Opinion"
    OTHER = "Other"


class JudgeVerdict(BaseModel):
    should_engage: bool = Field(..., description="True if the post is worth commenting on.")
    category: PostCategory
    language: str = Field(..., description="Detected language code: 'pt-br', 'en', 'es', etc.")
    reasoning: str = Field(..., description="Brief reason for approval/rejection.")


class Judge:
    """
    The first layer of the sequential chain.
    Performs fast semantic filtering with minimal token usage.
    """

    def __init__(self):
        self.logger = NetBotLoggerAdapter(logger, {'stage': 'C', 'status_code': 'JUDGE'})
        self.agent = Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Post Relevance Judge",
            instructions=self._build_system_prompt(),
            output_schema=JudgeVerdict,
            markdown=True
        )

    def _build_system_prompt(self) -> str:
        return """You are a content filter for a senior software engineer's social media bot.
Your ONLY job is to decide if a post is worth engaging with and categorize it.

## REJECT if the post is about:
- Finance, investments, crypto trading
- Politics or political opinions
- Religion or spiritual content
- Sales pitches, product promotions, or affiliate marketing
- Memes without technical depth
- Generic motivational/self-help content ("Rise and grind", "Believe in yourself")
- Content you cannot understand or that is too vague

## APPROVE if the post is about:
- Software engineering, coding, architecture
- AI, machine learning, data science
- Tech industry trends, startups
- Career development IN TECH (not generic career advice)
- Developer tools, frameworks, languages
- System design, DevOps, cloud
- Open source projects
- Technical opinions or hot takes

## LANGUAGE DETECTION
Detect the language of the post. Use ISO codes: 'pt-br' for Brazilian Portuguese, 'en' for English, 'es' for Spanish, etc.

Be decisive. When in doubt, REJECT."""

    def evaluate(self, post: SocialPost) -> JudgeVerdict:
        """
        Evaluates a post and returns a verdict.
        This is a lightweight call — no persona, no RAG, no dossier.
        """
        prompt = f"""Analyze this {post.platform.value} post:
- Author: @{post.author.username}
- Content: "{post.content}"
- Media Type: {post.media_type}

Should we engage with this post? Categorize it and detect the language."""

        self.logger.info(f"⚖️ Judging post {post.id} by @{post.author.username}...")

        # HARD FILTER: Block Companies/Schools on LinkedIn
        if post.platform.value == "linkedin":
            is_company = False
            # Check 1: Profile URL structure
            if post.author.profile_url:
                if "/company/" in post.author.profile_url or "/school/" in post.author.profile_url:
                    is_company = True
            
            # Check 2: Username heuristic (posts/feed patterns often seen in company scrape)
            # e.g. "google/posts" -> company
            if post.author.username and "/posts" in post.author.username:
                 is_company = True

            if is_company:
                self.logger.info(f"🚫 Hard Block: Company/Organization detected (@{post.author.username})")
                return JudgeVerdict(
                    should_engage=False,
                    category=PostCategory.OTHER,
                    language="en", 
                    reasoning="Hard Block: Post is from a Company or School page (not a person)."
                )

        try:
            response_obj = self.agent.run(prompt)
            verdict: JudgeVerdict = response_obj.content

            # Log to DB
            from core.database import db
            run_metrics = getattr(response_obj, 'metrics', None)
            token_metrics = {
                "input_tokens": getattr(run_metrics, 'input_tokens', 0) if run_metrics else 0,
                "output_tokens": getattr(run_metrics, 'output_tokens', 0) if run_metrics else 0,
                "total_cost": getattr(run_metrics, 'cost', 0.0) if run_metrics else 0.0
            }
            db.log_llm_interaction(
                provider="openai",
                model="gpt-4o-mini",
                system_prompt=self.agent.instructions if isinstance(self.agent.instructions, str) else "Judge Instructions",
                user_prompt=prompt,
                response=verdict.model_dump_json(),
                parameters={"temperature": 0.0},
                metrics=token_metrics,
                metadata={
                    "layer": "judge",
                    "post_id": post.id,
                    "platform": post.platform.value,
                    "author": post.author.username,
                    "verdict": verdict.should_engage,
                    "category": verdict.category.value
                }
            )

            emoji = "✅" if verdict.should_engage else "❌"
            self.logger.info(
                f"{emoji} Verdict: {verdict.should_engage} | "
                f"Category: {verdict.category.value} | "
                f"Lang: {verdict.language} | "
                f"Reason: {verdict.reasoning}"
            )
            return verdict

        except Exception as e:
            self.logger.error(f"Judge error: {e}")
            # Fail safe: approve on error to avoid silent skipping
            return JudgeVerdict(
                should_engage=True,
                category=PostCategory.OTHER,
                language="en",
                reasoning=f"Judge error (fail-open): {e}"
            )
