
import os
import sys
import logging
import feedparser
import json
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.database import db
from agno.agent import Agent
from agno.models.openai import OpenAIChat

from core.logger import logger

class NewsFetcher:
    def __init__(self):
        self.sources = self._load_sources()
        self.agent = self._create_agent()

    def _load_sources(self) -> List[Dict]:
        """Loads RSS sources from config/sources.json"""
        sources_path = settings.CONFIG_DIR / "sources.json"
        if not sources_path.exists():
            logger.warning("No sources.json found. Using defaults.")
            return []
        
        try:
            with open(sources_path, "r") as f:
                return [s for s in json.load(f) if s.get("enabled", True)]
        except Exception as e:
            logger.error(f"Error loading sources: {e}")
            return []

    class NewsDecision(BaseModel):
        approved: bool = Field(..., description="Set to True if the content is approved.")
        reasoning: str = Field(..., description="Reason for approval/rejection.")
        summary: Optional[str] = Field(None, description="TL;DR summary if approved.")
        key_points: Optional[List[str]] = Field(None, description="List of key points if approved.")

    def _create_agent(self) -> Agent:
        """Creates the Gatekeeper/Summarizer Agent"""
        
        # Load Persona for context
        persona_path = settings.BASE_DIR / "docs" / "persona" / "persona.md"
        try:
            with open(persona_path, "r") as f:
                persona_content = f.read()
        except:
            persona_content = "You are a tech-savvy engineer."

        system_prompt = f"""
        {persona_content}
        
        ## ROLE: THE GATEKEEPER & SUMMARIZER
        You are responsible for curating content for a technical audience.
        
        ## TASK 1: FILTERING (Gatekeeper)
        Analyze the provided article title and snippet.
        - Does this fit my interests (AI, Engineering, Tech Trends, Startups, Coding)?
        - Is it high quality? (Skip clickbait, generic marketing, or irrelevant political news).
        
        ## TASK 2: SUMMARIZATION
        If the content is approved:
        1. "TL;DR": A 1-sentence punchy summary.
        2. "Key Points": 3 bullet points extracting the most valuable insights.
        """
        
        return Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            description="News Curator",
            instructions=system_prompt,
            output_schema=self.NewsDecision,
            markdown=True
        )

    def fetch_and_process(self):
        """Main execution loop"""
        logger.info(f"Starting fetch cycle for {len(self.sources)} sources...")
        
        total_fetched = 0
        total_approved = 0
        
        for source in self.sources:
            url = source["url"]
            name = source["name"]
            logger.debug(f"Fetching {name} ({url})...")
            
            try:
                feed = feedparser.parse(url)
                
                # Check closest 5 entries
                for entry in feed.entries[:10]:
                    link = entry.get("link")
                    title = entry.get("title")
                    snippet = entry.get("summary", "")[:500] # Truncate snippet
                    
                    if not link or not title:
                        continue

                    # 1. Deduplication Check
                    if self._is_processed(link):
                        logger.debug(f"Skipping known link: {link}")
                        continue
                    
                    # 2. AI Processing
                    logger.debug(f"Analyzing: {title}")
                    decision = self._analyze_content(title, snippet, name)
                    
                    if decision.get("approved"):
                        self._save_to_db(entry, decision, name)
                        total_approved += 1
                        logger.info(f"✅ Approved: {title}")
                    else:
                        logger.debug(f"❌ Rejected: {decision.get('reasoning')}")
                    
                    # Mark as processed regardless of approval? 
                    # Currently strict dedup only checks DB. If rejected, we don't save to DB 
                    # which means we might re-process it next run.
                    # Ideally we should save 'rejected' too to avoid costs.
                    # Let's save as 'rejected' if rejected.
                    if not decision.get("approved"):
                         self._save_rejection(entry, decision, name)

                    total_fetched += 1
                    
            except Exception as e:
                logger.error(f"Error processing source {name}: {e}")

        logger.info(f"Cycle Complete. Fetched {total_fetched}, Approved {total_approved}.")

    def _is_processed(self, url: str) -> bool:
        """Checks if URL exists in content_ideas table"""
        try:
            res = db.client.table("content_ideas").select("id").eq("source_url", url).execute()
            return len(res.data) > 0
        except Exception as e:
            logger.error(f"DB Check Error: {e}")
            return False # Fail safe: try to process? Or True to skip? False risks duplicate cost.

    def _analyze_content(self, title: str, snippet: str, source_name: str) -> Dict:
        """Calls OpenAI to filter and summarize"""
        prompt = f"""
        Source: {source_name}
        Title: {title}
        Snippet: {snippet}
        """
        try:
            response = self.agent.run(prompt)
            data = response.content
            if isinstance(data, self.NewsDecision):
                return data.model_dump()
            if isinstance(data, dict):
                return data
            if isinstance(data, str):
                return json.loads(data)
            return {"approved": False, "reasoning": "Unknown response format"}
        except Exception as e:
            logger.error(f"AI Error: {e}")
            return {"approved": False, "reasoning": f"AI Error: {e}"}

    def _save_to_db(self, entry, decision, source_name):
        """Saves approved content to DB"""
        try:
            summary_text = f"TL;DR: {decision.get('summary')}\n\nKey Points:\n" + "\n".join([f"- {p}" for p in decision.get("key_points", [])])
            
            data = {
                "source_url": entry.get("link"),
                "title": entry.get("title"),
                "summary": summary_text,
                "original_content": entry.get("summary", "")[:1000],
                "type": "news",
                "status": "pending",
                "metadata": {
                    "source_name": source_name,
                    "published": entry.get("published"),
                    "ai_reasoning": decision.get("reasoning")
                }
            }
            db.client.table("content_ideas").insert(data).execute()
        except Exception as e:
            logger.error(f"DB Save Error: {e}")

    def _save_rejection(self, entry, decision, source_name):
        """Saves rejected content to DB to avoid re-processing cost"""
        try:
             data = {
                "source_url": entry.get("link"),
                "title": entry.get("title"),
                "summary": None,
                "type": "news",
                "status": "rejected",
                "metadata": {
                    "source_name": source_name,
                    "ai_reasoning": decision.get("reasoning")
                }
            }
             db.client.table("content_ideas").insert(data).execute()
        except Exception as e:
            logger.error(f"DB Save Rejection Error: {e}")

if __name__ == "__main__":
    fetcher = NewsFetcher()
    fetcher.fetch_and_process()
