
import os
import sys
import json
import random
import logging
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.database import db
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from core.logger import logger

class ProjectUpdateGenerator:
    def __init__(self):
        self.agent = self._create_agent()

    def _create_agent(self) -> Agent:
        # Load Persona
        persona_path = settings.BASE_DIR / "docs" / "persona" / "persona.md"
        try:
            with open(persona_path, "r") as f:
                persona_content = f.read()
        except:
            persona_content = "You are a tech-savvy engineer."

        instructions = f"""
        {persona_content}
        
        ## ROLE: PROJECT CURATOR
        Your goal is to generate an engaging technical update about a specific project challenge.
        
        ## TASK
        Based on the project name, stack, and a recent challenge, generate a post idea.
        The post should:
        1.  Mention the challenge in a "No-Bullshit" direct way.
        2.  Connect the challenge with the technical stack.
        3.  Provide a technical insight or a "lesson learned".
        
        Output format:
        Return a JSON with:
        - "title": A punchy technical title.
        - "content": The post content (150-300 characters).
        - "reasoning": Why this is a good post for the audience.
        """
        
        return Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="Project Update Content Creator",
            instructions=instructions,
            markdown=True
        )

    def _should_generate(self) -> bool:
        """Checks if a project update was created in the last 7 days"""
        try:
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            res = db.client.table("content_ideas") \
                .select("id") \
                .eq("type", "project_update") \
                .gte("created_at", seven_days_ago) \
                .execute()
            return len(res.data) == 0
        except Exception as e:
            logger.error(f"Error checking recent updates: {e}")
            return True

    def run(self, force: bool = False):
        if not force and not self._should_generate():
            logger.debug("Project update already generated this week. Skipping.")
            return

        # Fetch projects from DB
        try:
            res = db.client.table("projects").select("*").eq("enabled", True).execute()
            projects = res.data
        except Exception as e:
            logger.error(f"Failed to fetch projects from DB: {e}")
            return

        if not projects:
            logger.warning("No active projects found in database.")
            return

        project = random.choice(projects)
        logger.info(f"Generating update for project: {project['name']}")

        prompt = f"""
        Project: {project['name']}
        Stack: {project['stack']}
        Challenge: {project['recent_challenge']}
        """

        try:
            response = self.agent.run(prompt)
            data = response.content
            
            if isinstance(data, str):
                try:
                    content_data = json.loads(data)
                except:
                    content_data = {"title": f"Update: {project['name']}", "content": data, "reasoning": "Direct agent output"}
            else:
                content_data = data

            self._save_to_pool(project, content_data)
        except Exception as e:
            logger.error(f"AI Error: {e}")

    def _save_to_pool(self, project, content_data):
        try:
            data = {
                "source_url": f"db_project_{project['id']}",
                "title": content_data.get("title", f"Update: {project['name']}"),
                "summary": content_data.get("content"),
                "original_content": project['recent_challenge'],
                "type": "project_update",
                "status": "pending",
                "metadata": {
                    "project_name": project['name'],
                    "stack": project['stack'],
                    "ai_reasoning": content_data.get("reasoning")
                }
            }
            db.client.table("content_ideas").insert(data).execute()
            logger.info(f"✅ Project update saved for {project['name']}")
        except Exception as e:
            logger.error(f"DB Save Error: {e}")

if __name__ == "__main__":
    generator = ProjectUpdateGenerator()
    generator.run()
