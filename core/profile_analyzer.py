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
    summary: str = Field(..., description="Brief summary of the profile.")
    technical_level: TechnicalLevel = Field(...)
    job_title: str = Field(..., description="Likely job role or position.")
    is_hype_seller: bool = Field(..., description="True if the user sells 'hype' without substance.")
    tone_preference: str = Field(..., description="Detected tone preference.")
    interests: List[str] = Field(..., description="Main topics of interest.")
    interaction_guidelines: str = Field(..., description="Specific tactical advice for Guilherme's response.")

class ProfileAnalyzer:
    def __init__(self):
        self.agent = Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Profile Analyst",
            instructions="""You are the Profile Analyst for Guilherme Lorenz, a Senior Software Engineer and founder of Klotar Studio. 
Your mission is to dissect social media profiles through Guilherme's eyes, focusing on technical pragmatism, product vision, and robustness.

## GUILHERME'S IDENTITY CONTEXT:
- 13 years in IT; Senior .NET/C# Expert; Rare hybrid of Product Design and Engineering.
- Core Values: SOLID, Clean Architecture (when needed), Monoliths over unnecessary Microservices, Latency is UX.
- Common Enemies: "Prompt Devs" (no logic), Showcase Complexity (overengineering), and "Hype Sellers".

## YOUR GOAL:
Analyze the provided bio and recent posts to create a professional and psychological dossier. 
Determine if the user is a technical peer, a junior needing mentorship, or a "Hype Seller" (vendedor de fumaça).""",
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
            Analyze this user profile based on Guilherme Lorenz's standards:

            - Username: @{profile.username}
            - Bio: "{profile.bio or 'No bio'}"
            - Followers: {profile.follower_count or 'Unknown'}

            ## RECENT POSTS:
            {posts_block}

            ## ANALYSIS REQUIREMENTS:
            1. DETECT "HYPE SELLERS": Flag as 'is_hype_seller' if they promote "get rich quick" tech schemes, grind culture without technical depth, or flashy tools without architectural substance.
            2. JOB TITLE (LinkedIn Focus): Identify their likely professional role (e.g., CTO, Recruiter, Junior Dev, etc.).
            3. TECHNICAL DEPTH: Evaluate if they understand the "why" or just repeat buzzwords.
            4. INTERACTION STRATEGY: 
               - If Junior: Be a pragmatic mentor (can use "garoteou" for basic mistakes).
               - If Peer/Senior: Technical debate, peer-to-peer.
               - If Hype Seller: Be acidic, ironic, and call out the "smoke".

            Generate a dossier that enables Guilherme to engage with 7-8/10 intensity.
            """
            
            logger.info(f"Analyzing profile @{profile.username}...")
            response_obj = self.agent.run(user_input)
            
            # Agno returns the Pydantic object directly in content if output_schema is set
            dossier: ProfileDossier = response_obj.content
            
            # Log full dossier for review (JSON format)
            logger.info(f"Dossier generated for @{profile.username}:\n{dossier.model_dump_json(indent=2)}")
            return dossier

        except Exception as e:
            logger.error(f"Error analyzing profile @{profile.username}: {e}")
            return None
