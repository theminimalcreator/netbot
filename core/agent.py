import json
from typing import Optional, List
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from config.settings import settings
from core.logger import logger
from core.models import SocialPost, ActionDecision, SocialPlatform
from core.knowledge_base import NetBotKnowledgeBase
from core.profile_analyzer import ProfileDossier

# --- Structured Output Schema ---
# We reuse ActionDecision from models, but Agno might need a Pydantic model for output parsing
# So we keep a specific output model and map it later, or use valid Pydantic models directly.

class AgentOutput(BaseModel):
    should_comment: bool = Field(..., description="Set to True if we should comment, False to skip.")
    comment_text: str = Field(..., description="The comment text. MUST be in English. No hashtags. Max 1 emoji. Avoid generic phrases.")
    reasoning: str = Field(..., description="Brief reason for the decision and the chosen comment.")

class SocialAgent:
    def __init__(self):
        self.prompts = settings.load_prompts()
        self.knowledge_base = NetBotKnowledgeBase()
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Configures the Agno Agent with GPT-4o-mini."""
        
        # Load Persona from Markdown
        persona_path = settings.BASE_DIR / "docs" / "persona" / "persona.md"
        try:
            with open(persona_path, "r", encoding="utf-8") as f:
                persona_content = f.read()
            logger.info(f"✅ Persona loaded from {persona_path} ({len(persona_content)} chars)")
            logger.debug(f"Persona Preview: {persona_content[:100]}...")
        except Exception as e:
            logger.error(f"❌ Failed to load persona from {persona_path}: {e}")
            persona_content = "You are a helpful social media assistant."

        system_prompt = f"""
        {persona_content}
        
        ## Your Goal
        Read the content, comments (context), and analyze media to generate a contextual, authentic engagement.
        
        ## IMPORTANT: BEHAVIOR GUIDELINES
        1. **OPINION OVER SOLUTION**: Do NOT try to solve complex coding problems or debugging issues in the comments. You are a senior engineer giving a "hot take" or advice, not a compiler.
        2. **AVOID HALLUCINATIONS**: If you don't know the specific details of a library or bug, do not invent them. Stick to high-level architectural advice or clean code principles.
        3. **SHORT & IMPACTFUL**: Your comments should be like a tweet or a short LinkedIn reply. High signal, low noise.
        4. **NO GENERIC PRAISE**: Avoid comments like "Great design clarity!", "Love the aesthetics!", "Bridging tech and usability" or "Harmonizing aesthetics with performance". If you don't understand the post, choose NOT to comment.
        5. **NEGATIVE CONSTRAINTS**:
           - DO NOT use the phrase "design clarity".
           - DO NOT use the phrase "bridging tech and usability".
           - DO NOT use the phrase "harmonizing aesthetics".
           - DO NOT use the word "tapestry".
        
        ## IMPORTANT: Learning from History
        1. **SEARCH KNOWLEDGE BASE**: Search your knowledge base ONCE for similar posts you've interacted with.
        2. **STOP SEARCHING**: If you find relevant examples, use them. If not, proceed with your best judgment. Do NOT search again.
        3. **ADOPT STYLE**: Look at your past comments on those posts. Match that specific tone (e.g., if you were witty before, be witty now).
        4. **CONSISTENCY**: If you have expressed an opinion on a topic before, stick to it.
        """
        
        return Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Social Engagement Agent",
            instructions=system_prompt,
            output_schema=AgentOutput,
            knowledge=self.knowledge_base,
            search_knowledge=True,
            markdown=True
        )

    def decide_and_comment(self, post: SocialPost, dossier: Optional[ProfileDossier] = None) -> ActionDecision:
        """
        Analyzes a candidate post and returns an ActionDecision.
        """
        try:
            # Prepare Input
            comments_context = ""
            if post.comments:
                formatted_comments = "\n".join([f"- @{c.author.username}: {c.text}" for c in post.comments])
                comments_context = f"\nRecent Comments (for context):\n{formatted_comments}"

            # Prepare Dossier Context
            dossier_context = ""
            if dossier:
                dossier_context = f"""
                ## TARGET AUDIENCE DOSSIER (@{post.author.username})
                - Summary: {dossier.summary}
                - Technical Level: {dossier.technical_level}
                - Interests: {', '.join(dossier.interests)}
                - Tone Preference: {dossier.tone_preference}
                - INTERACTION GUIDELINES: {dossier.interaction_guidelines}
                
                IMPORTANT: Adapt your response to match this person's level and tone.
                """

            # Determines constraints based on platform
            char_limit = "280 characters" if post.platform == SocialPlatform.TWITTER else "proportional to the post length"
            
            if post.platform == SocialPlatform.TWITTER:
                style_guide = "Style: Use abbreviations if needed, no hashtags unless relevant, casual but professional."
            elif post.platform == SocialPlatform.THREADS:
                style_guide = "Style: Conversational, threading-friendly, casual."
            elif post.platform == SocialPlatform.LINKEDIN:
                style_guide = "Style: Professional, constructive, slightly more formal."
            elif post.platform == SocialPlatform.DEVTO:
                style_guide = "Style: Technical, in-depth, explanatory, code-friendly, professional."
            else:
                style_guide = "Style: Casual, helpful, Instagram-native."

            user_input = f"""
            Analyze this {post.platform.value} Post:
            - Author: @{post.author.username}
            - Content: "{post.content}"
            - Media Type: {post.media_type}
            {dossier_context}
            {comments_context}
            
            Determine if I should comment. If yes, write the comment.
            - Constraint: Max {char_limit}.
            - {style_guide}
            """
            
            logger.info(f"Agent analyzing post {post.id} by {post.author.username} on {post.platform.value}...")
            
            # Try to pass image URL directly in the prompt if available
            image_url_log = "None"
            if post.media_urls:
                # Assuming simple support for the first image for now
                user_input += f"\n\nImage URL (for context): {post.media_urls[0]}"
                image_url_log = post.media_urls[0]
            
            # --- LOGGING WHAT THE AI SEES ---
            logger.info(f"👀 AI INPUT DATA via {post.id}:\n   -> Content: {post.content[:200]}...\n   -> Image: {image_url_log}")

            # Run agent
            response_obj = self.agent.run(user_input)
            response: AgentOutput = response_obj.content
            
            # Log Token Usage if available
            if hasattr(response_obj, 'metrics') and response_obj.metrics:
                logger.info(f"💰 Token Usage: {response_obj.metrics}")
            
            logger.info(f"Agent Decision: Comment={response.should_comment} | Reasoning: {response.reasoning}")
            
            return ActionDecision(
                should_act=response.should_comment,
                content=response.comment_text,
                reasoning=response.reasoning,
                action_type="comment",
                platform=post.platform
            )

        except Exception as e:
            logger.error(f"Agent Malfunction: {e}")
            return ActionDecision(should_act=False, reasoning=f"Error: {e}")

# agent = SocialAgent() # Instantiation moved to main.py to avoid side effects on import
