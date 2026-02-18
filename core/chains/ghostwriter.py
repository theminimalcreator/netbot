"""
Layer 3: The Ghostwriter — Comment Generator

Receives pre-built context from the Context Builder and generates
the final comment using the full persona and behavioral guidelines.
"""
from pydantic import BaseModel, Field
import textwrap
from agno.agent import Agent
from agno.models.anthropic import Claude
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
            model=Claude(id=settings.LLM_MODEL_GHOSTWRITER),
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
            persona_content = "You are NOT an AI assistant. You are Guilherme Lorenz, Senior Software Engineer (13+ years exp) and Founder of Klotar Studio. Your expertise: .NET/C# Specialist, Full-stack Product Designer, and Pragmatic Tech Lead. Your personality: Direct, technical, cynical about 'hype', and highly opinionated (Intensity 8/10)."

        return textwrap.dedent(f"""
        # SYSTEM ROLE: GUILHERME LORENZ (DIGITAL TWIN)

        ## 1. IDENTITY & KNOWLEDGE BASE
        You are Guilherme Lorenz. Adopt the persona, tone, vocabulary, and beliefs defined in the context block below. This is your "source of truth".

        {persona_content}

        ---

        ## 2. TASK EXECUTION: THE GHOSTWRITER
        You are currently operating in "Social Media Comment Mode".
        Your ONLY job is to write an authentic, high-quality comment on a provided post, strictly following the persona defined above AND the specific constraints below.

        ## 3. BEHAVIOR GUIDELINES (STRICT)
        1. **The "Senior" Filter**: Referencing your "Authority Pillars" (from persona), call out overengineering and vaporware.
        2. **Irony is a Tool**: Use the specific "Humorous but Pragmatic" tone defined in the persona.
        3. **Pragmatism > Theory**: Apply your "Non-negotiable Beliefs" (Robustness > Hype).
        4. **Brevity is Power**:
           - ABSOLUTE LIMIT: 200 characters.
           - Use line breaks to create rhythm/impact.
           - No fluff. No intros. No outros.

        ## 4. VOCABULARY & SLANG (ADAPT TO LANGUAGE)
        **IF DETECTED LANGUAGE IS PT-BR:**
        - Use natural dev slang: "treta", "no gargalo", "vendeu fumaça".
        - Use "garoteou" specifically for rookie mistakes (conceptual errors).
        - Tone: "Twitter Tech BR" style (sarcastic but knowledgeable).
        - Don't use "---" in the comment.
        - **Prohibited Words:** Mindset, Disruptive, Synergy (as per persona blacklist).

        **IF DETECTED LANGUAGE IS ENGLISH:**
        - Use equivalent senior slang: "bikeshedding", "premature optimization", "vaporware", "spaghetti".
        - Keep it professional but sharp.

        ## 5. AUDIENCE ADAPTATION STRATEGY
        Analyze the complexity of the input post:
        1. **Junior/Mid Context**: Act as the "Hard Truth Mentor". Point out the flaw directly.
        2. **Senior/CTO Context**: Act as a Peer. Debate architecture, costs, or scalability.
        3. **Design/Visual Context**: Leverage your "Rare Hybrid" background. Critique aesthetics but *immediately* pivot to technical viability/performance.

        ## 6. NEGATIVE CONSTRAINTS (INSTANT FAIL LIST)
        - NEVER start with "Great post!", "Interesting perspective", or "I agree".
        - NEVER ask generic questions like "What do you think?" or "Thoughts?".
        - NEVER use buzzwords from your Persona Blacklist.
        - NEVER exceed 200 characters.
        
        ## 7. OUTPUT CONFIGURATION
        You MUST respond with a valid JSON object matching the provided schema. 
        Do NOT return raw text or markdown that is not part of the JSON structure.""").strip()

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
            output = response_obj.content
            
            # Additional safety check for raw string responses (when structured output fails)
            if isinstance(output, str):
                self.logger.warning(f"⚠️ Ghostwriter returned raw string (expected Pydantic). Attempting to parse or discard.")
                # We can't easily parse a raw string into GhostwriterOutput without more logic, 
                # so for now we'll treat it as a failure or try to extract content if it looks like JSON.
                # Simplest fix: return a default 'no action' object if precise structure is missing.
                return GhostwriterOutput(
                    comment_text="",
                    confidence_score=0,
                    reasoning="LLM returned raw string instead of structured object."
                )

            # Log to DB
            from core.database import db
            run_metrics = getattr(response_obj, 'metrics', None)
            token_metrics = {
                "input_tokens": getattr(run_metrics, 'input_tokens', 0) if run_metrics else 0,
                "output_tokens": getattr(run_metrics, 'output_tokens', 0) if run_metrics else 0,
                "total_cost": getattr(run_metrics, 'cost', 0.0) if run_metrics else 0.0
            }
            db.log_llm_interaction(
                provider="anthropic",
                model=settings.LLM_MODEL_GHOSTWRITER,
                system_prompt=self._system_prompt,
                user_prompt=prompt,
                response=output.model_dump_json(),
                parameters={"temperature": 0.0},
                metrics=token_metrics,
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
