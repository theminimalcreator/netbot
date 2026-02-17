"""
Layer 3: The Ghostwriter — Comment Generator

Receives pre-built context from the Context Builder and generates
the final comment using the full persona and behavioral guidelines.
"""
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from config.settings import settings
from core.logger import logger, NetBotLoggerAdapter
from core.chains.context_builder import EngagementContext


class GhostwriterOutput(BaseModel):
    comment_text: str = Field(..., description="The comment text. Match the detected language. NO hashtags. Max 1 emoji. Avoid generic phrases.")
    confidence_score: int = Field(..., description="0-100 score of how confident you are in this comment.")
    reasoning: str = Field(..., description="Brief reason for the chosen comment tone and content.")


class Ghostwriter:
    """
    The final layer of the sequential chain.
    Generates the actual comment using full persona context + pre-built engagement context.
    """

    def __init__(self):
        self.logger = NetBotLoggerAdapter(logger, {'stage': 'C', 'status_code': 'WRITER'})
        self._system_prompt = self._build_system_prompt()
        self.agent = Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Social Ghostwriter",
            instructions=self._system_prompt,
            output_schema=GhostwriterOutput,
            markdown=True
        )

    def _build_system_prompt(self) -> str:
        # Load Persona
        persona_path = settings.BASE_DIR / "docs" / "persona" / "persona.md"
        try:
            with open(persona_path, "r", encoding="utf-8") as f:
                persona_content = f.read()
        except Exception as e:
            self.logger.error(f"Failed to load persona: {e}")
            persona_content = "You are a senior software engineer and tech influencer."

        return f"""{persona_content}

## YOUR ROLE: THE GHOSTWRITER
You receive pre-analyzed context about a social media post. Your ONLY job is to write
an authentic, high-quality comment that matches the persona.

## BEHAVIOR GUIDELINES
1. **OPINION OVER SOLUTION**: Do NOT solve coding problems. Give "hot takes" or architectural advice.
2. **AVOID HALLUCINATIONS**: If you don't know specifics, stick to high-level advice.
3. **SHORT & IMPACTFUL**: High signal, low noise. Like a tweet or short LinkedIn reply.
4. **NO GENERIC PRAISE**: Never say things like "Great design clarity!", "Love the aesthetics!",
   "Bridging tech and usability", or "Harmonizing aesthetics with performance".
   If you don't understand the post well enough to add value, set confidence_score below 50.

## NEGATIVE CONSTRAINTS
- DO NOT use the phrase "design clarity".
- DO NOT use the phrase "bridging tech and usability".
- DO NOT use the phrase "harmonizing aesthetics".
- DO NOT use the word "tapestry".

## LANGUAGE RULE
You will receive the detected language of the post. ALWAYS reply in that language.
If language is "pt-br", reply in Brazilian Portuguese. Otherwise reply in English.

## CONSISTENCY
If past interactions are provided, validate your opinion against them.
Match the tone from your past comments on similar topics."""

    def write(self, context: EngagementContext) -> GhostwriterOutput:
        """
        Generates a comment based on the pre-built engagement context.
        """
        # Build the user prompt from context
        sections = [
            f"## POST ({context.platform.value})",
            f"Author: @{context.author_username}",
            f'Content: "{context.content}"',
            f"Category: {context.category} | Language: {context.language}",
            "",
            "## SIGNALS",
            f"Engagement: {context.engagement_signal} ({context.reply_count} replies, {context.like_count} likes)",
            f"Strategy: {context.strategy}",
        ]

        if context.dossier_block:
            sections.extend(["", "## TARGET AUDIENCE DOSSIER", context.dossier_block])

        if context.rag_block:
            sections.extend(["", "## PAST INTERACTIONS (CONSISTENCY CHECK)", context.rag_block])

        if context.comments_block:
            sections.extend(["", "## EXISTING COMMENTS", context.comments_block])

        if context.media_urls:
            sections.extend(["", f"Image URL (for context): {context.media_urls[0]}"])

        sections.extend([
            "",
            "---",
            f"Write the comment. Max {context.char_limit}. Style: {context.style_guide}."
        ])

        prompt = "\n".join(sections)

        self.logger.info(f"✍️ Ghostwriter generating comment for {context.post_id}...")

        try:
            response_obj = self.agent.run(prompt)
            output: GhostwriterOutput = response_obj.content

            # Log to DB
            from core.database import db
            metrics_raw = getattr(response_obj, 'metrics', {})
            db.log_llm_interaction(
                provider="openai",
                model="gpt-4o-mini",
                system_prompt=self._system_prompt,
                user_prompt=prompt,
                response=output.model_dump_json(),
                parameters={"temperature": 0.0},
                metrics={
                    "input_tokens": metrics_raw.get('input_tokens', 0),
                    "output_tokens": metrics_raw.get('output_tokens', 0),
                    "total_cost": metrics_raw.get('total_cost', 0.0)
                },
                metadata={
                    "layer": "ghostwriter",
                    "post_id": context.post_id,
                    "platform": context.platform.value,
                    "author": context.author_username,
                    "confidence": output.confidence_score
                }
            )

            self.logger.info(
                f"📝 Comment generated (Conf: {output.confidence_score}%): "
                f"{output.comment_text[:80]}..."
            )
            return output

        except Exception as e:
            self.logger.error(f"Ghostwriter error: {e}")
            return GhostwriterOutput(
                comment_text="",
                confidence_score=0,
                reasoning=f"Ghostwriter error: {e}"
            )
