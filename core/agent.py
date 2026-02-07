import json
from typing import Optional, List
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from config.settings import settings
from core.logger import logger

# --- Structured Output Schema ---
class PostAction(BaseModel):
    should_comment: bool = Field(..., description="Set to True if we should comment, False to skip (sensitive content/boring/irrelevant).")
    comment_text: str = Field(..., description="The comment text. MUST be in Portuguese (Brazil). No hashtags. Max 1 emoji. Avoid generic phrases.")
    reasoning: str = Field(..., description="Brief reason for the decision and the chosen comment.")

class InstagramAgent:
    def __init__(self):
        self.prompts = settings.load_prompts()
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        """Configures the Agno Agent with GPT-4o-mini."""
        
        # Construct System Prompt from YAML
        persona = self.prompts.get("persona", {})
        constraints = self.prompts.get("constraints", {})
        
        system_prompt = f"""
        You are an Instagram User interacting with posts.
        Role: {persona.get('role', 'User')}
        Tone: {persona.get('tone', 'Casual')}
        Language: {persona.get('language', 'pt-BR')}
        
        Style Guidelines:
        {json.dumps(persona.get('style_guidelines', []), indent=2)}
        
        Constraints:
        {json.dumps(constraints, indent=2)}
        
        Your Goal: Read the caption, comments (context), and analyze the image to generate a contextual, authentic engagement.
        """
        
        return Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Instagram Engagement Agent",
            instructions=system_prompt,
            output_schema=PostAction,
            markdown=True
        )

    def decide_and_comment(self, candidate: dict) -> Optional[PostAction]:
        """
        Analyzes a candidate post and returns a PostAction.
        """
        try:
            # Prepare Input
            comments_context = ""
            if candidate.get('comments'):
                formatted_comments = "\n".join([f"- @{c['username']}: {c['text']}" for c in candidate['comments']])
                comments_context = f"\nRecent Comments (for context):\n{formatted_comments}"

            user_input = f"""
            Analyze this Instagram Post:
            - Author: @{candidate['username']}
            - Caption: "{candidate['caption']}"
            - Media Type: {candidate.get('media_type')}
            {comments_context}
            
            Determine if I should comment. If yes, write the comment.
            """
            
            logger.info(f"Agent analyzing post {candidate['media_id']} by {candidate['username']}...")
            logger.info(f"📝 Caption: {candidate.get('caption', 'EMPTY')[:200]}...")
            logger.info(f"🖼️  Image URL: {candidate.get('image_url', 'NONE')}")
            
            # Try to pass image URL directly in the prompt if available
            if candidate.get('image_url'):
                user_input += f"\n\nImage URL (for context): {candidate['image_url']}"
            
            # Run agent without images parameter (it was causing issues)
            response_obj = self.agent.run(user_input)
            response: PostAction = response_obj.content
            
            # Log Token Usage if available
            if hasattr(response_obj, 'metrics') and response_obj.metrics:
                logger.info(f"💰 Token Usage: {response_obj.metrics}")
            
            logger.info(f"Agent Decision: Comment={response.should_comment} | Reasoning: {response.reasoning}")
            return response

        except Exception as e:
            logger.error(f"Agent Malfunction: {e}")
            return None

agent = InstagramAgent()
