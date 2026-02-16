import json
from typing import Optional, List
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from config.settings import settings
from core.logger import logger, NetBotLoggerAdapter
from core.models import SocialPost, ActionDecision, SocialPlatform
from core.knowledge_base import NetBotKnowledgeBase
from core.profile_analyzer import ProfileDossier

# --- Structured Output Schema ---
# We reuse ActionDecision from models, but Agno might need a Pydantic model for output parsing
# So we keep a specific output model and map it later, or use valid Pydantic models directly.

class AgentOutput(BaseModel):
    should_comment: bool = Field(..., description="Set to True if we should comment, False to skip.")
    confidence_score: int = Field(..., description="0-100 score of how confident you are in this action.")
    comment_text: str = Field(..., description="The comment text. If post is in Portuguese, use PT-BR. Otherwise, use English. NO hashtags. Max 1 emoji. Avoid generic phrases.")
    reasoning: str = Field(..., description="Brief reason for the decision and the chosen comment.")

class SocialAgent:
    def __init__(self):
        self.prompts = settings.load_prompts()
        self.knowledge_base = NetBotKnowledgeBase()
        self.logger = NetBotLoggerAdapter(logger, {'stage': 'C', 'status_code': 'BRAIN'})
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Configures the Agno Agent with GPT-4o-mini."""
        
        # Load Persona from Markdown
        persona_path = settings.BASE_DIR / "docs" / "persona" / "persona.md"
        try:
            with open(persona_path, "r", encoding="utf-8") as f:
                persona_content = f.read()
            self.logger.debug(f"✅ Persona loaded from {persona_path} ({len(persona_content)} chars)")
        except Exception as e:
            self.logger.error(f"❌ Failed to load persona from {persona_path}: {e}")
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
        1. **CONSISTENCY**: Validate your opinion against provided Past Interactions. If you have expressed an opinion on a topic before, stick to it.
        2. **ADOPT STYLE**: Look at your past comments on those posts. Match that specific tone.
        """
        
        return Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Social Engagement Agent",
            instructions=system_prompt,
            output_schema=AgentOutput,
            knowledge=self.knowledge_base,
            search_knowledge=False, # We do manual RAG injection now for better control
            markdown=True
        )

    def decide_and_comment(self, post: SocialPost, dossier: Optional[ProfileDossier] = None) -> ActionDecision:
        """
        Analyzes a candidate post and returns an ActionDecision.
        """
        try:
            # 1. Prepare Input Context
            comments_context = ""
            if post.comments:
                formatted_comments = "\n".join([f"- @{c.author.username}: {c.text}" for c in post.comments])
                comments_context = f"\nRecent Comments (for context):\n{formatted_comments}"

            # 2. Prepare Dossier Context
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

            # 3. Analyze Metrics for "Hot Take" Opportunity
            metrics = getattr(post, 'metrics', {})
            reply_count = metrics.get('reply_count', 0)
            like_count = metrics.get('like_count', 0)
            
            engagement_signal = "Low"
            hot_take_instruction = "Kickstart the conversation. Be provocative but polite."
            
            if reply_count > 10:
                engagement_signal = "High"
                hot_take_instruction = "Join the flow. Reply to a specific point from existing comments (if valid)."
            elif reply_count > 0:
                engagement_signal = "Medium"
                hot_take_instruction = "Add a constructive perspective to the existing discussion."

            # 4. RAG: Search for Consistency
            # We search for the post content to find similar past topics
            past_takes = self.knowledge_base.search_similar_takes(post.content, limit=2)
            consistency_context = ""
            if past_takes:
                consistency_context = "\n## PAST INTERACTIONS (CONSISTENCY CHECK)\n" + "\n".join([f"- {take}" for take in past_takes])


            # 5. Build Final Prompt
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

            ## DONT COMMENT
            - If the post is about finance, DO NOT comment.
            - If the post is about politics, DO NOT comment.
            - If the post is about religion, DO NOT comment.
            - If the post is selling something, DO NOT comment.
            
            ## CONTEXT & SIGNALS
            - Engagement: {reply_count} replies, {like_count} likes.
            - Signal: {engagement_signal} Engagement.
            - Strategy: {hot_take_instruction}
            
            {dossier_context}
            {comments_context}
            {consistency_context}
            
            {consistency_context}
            
            Determine if I should comment. If yes, write the comment.
            - PROMPT: Detect the language of the post. If it is Portuguese, REPLY IN PORTUGUESE (PT-BR). For any other language, REPLY IN ENGLISH.
            - Constraint: Max {char_limit}.
            - {style_guide}
            """
            
            self.logger.info(f"Agent analyzing post {post.id} by {post.author.username} on {post.platform.value}...")
            
            # Try to pass image URL directly in the prompt if available
            image_url_log = "None"
            if post.media_urls:
                # Assuming simple support for the first image for now
                user_input += f"\n\nImage URL (for context): {post.media_urls[0]}"
                image_url_log = post.media_urls[0]
            
            # --- LOGGING WHAT THE AI SEES ---
            self.logger.info(f"👀 AI INPUT DATA via {post.id}:\n   -> Content: {post.content[:200]}...\n   -> Image: {image_url_log}")

            # Run agent
            response_obj = self.agent.run(user_input)
            response: AgentOutput = response_obj.content
            
            # Log Token Usage if available
            if hasattr(response_obj, 'metrics') and response_obj.metrics:
                self.logger.info(f"💰 Token Usage: {response_obj.metrics}", status_code='FINANCE')
            
            self.logger.info(f"Agent Decision: Comment={response.should_comment} (Conf: {response.confidence_score}%) | Reasoning: {response.reasoning}")
            
            # 6. Apply Confidence Filter
            should_act = response.should_comment
            if should_act and response.confidence_score < 70:
                self.logger.warning(f"⚠️ Confidence too low ({response.confidence_score}%). Skipping action.")
                should_act = False
                response.reasoning = f"[Low Confidence {response.confidence_score}%] {response.reasoning}"

            return ActionDecision(
                should_act=should_act,
                confidence_score=response.confidence_score,
                content=response.comment_text,
                reasoning=response.reasoning,
                action_type="comment",
                platform=post.platform
            )

        except Exception as e:
            self.logger.error(f"Agent Malfunction: {e}")
            return ActionDecision(should_act=False, reasoning=f"Error: {e}")

# agent = SocialAgent() # Instantiation moved to main.py to avoid side effects on import
