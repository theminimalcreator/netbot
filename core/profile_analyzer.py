import json
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from core.models import SocialProfile
from core.logger import logger

class TechnicalLevel(str, Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    EXPERT = "Expert"
    NON_TECHNICAL = "Non-Technical"

class ProfileDossier(BaseModel):
    summary: str = Field(..., description="Brief summary of who this person is.")
    technical_level: TechnicalLevel = Field(...)
    tone_preference: str = Field(..., description="Preferred tone (e.g., Casual, Formal, Sarcastic).")
    interests: List[str] = Field(..., description="Key topics they post about.")
    interaction_guidelines: str = Field(..., description="Specific advice on how to interact with them (e.g., 'Be concise', 'Use emojis', 'Cite sources').")

class ProfileAnalyzer:
    def __init__(self):
        self.agent = Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Profile Analyst",
            instructions="You are an expert social media analyst. Your goal is to analyze a user's profile (bio + posts) and create a deep psychological and professional dossier to guide future interactions.",
            output_schema=ProfileDossier,
            markdown=True
        )

    def analyze_profile(self, profile: SocialProfile) -> Optional[ProfileDossier]:
        """
        Analyzes a SocialProfile and returns a ProfileDossier.
        """
        if not profile:
            return None

        try:
            # Format the input for the LLM
            posts_text = []
            for i, post in enumerate(profile.recent_posts[:10]):
                posts_text.append(f"Post {i+1}: {post.content[:200]}...") # Truncate for token efficiency

            posts_block = "\n".join(posts_text)
            
            user_input = f"""
            Analyze this user profile:
            - Username: @{profile.username}
            - Bio: "{profile.bio or 'No bio'}"
            - Follower Count: {profile.follower_count or 'Unknown'}
            
            Recent Posts:
            {posts_block}
            
            Create a dossier that helps me (a senior software engineer bot) interact with them effectively.
            """
            
            logger.info(f"Analyzing profile @{profile.username}...")
            response_obj = self.agent.run(user_input)
            
            # Agno returns the Pydantic object directly in content if output_schema is set
            dossier: ProfileDossier = response_obj.content
            
            logger.info(f"Dossier generated for @{profile.username}: {dossier.summary[:50]}...")
            return dossier

        except Exception as e:
            logger.error(f"Error analyzing profile @{profile.username}: {e}")
            return None
