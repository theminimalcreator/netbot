"""
NetBot - Omnichannel AI Persona

Main entry point for the engagement bot.
Orchestrates multiple social network clients and the central AI agent.
Each platform runs sequentially: check limit → start → interact → close.
"""
import time
import random
import signal
import sys
import nest_asyncio
from datetime import datetime, timezone
nest_asyncio.apply()

from config.settings import settings
from core.database import db
from core.agent import SocialAgent
from core.logger import NetBotLoggerAdapter
# Base logger for main module
import logging
logger = NetBotLoggerAdapter(logging.getLogger("netbot"), {'status_code': 'SYSTEM'})
from core.browser_manager import BrowserManager

# Networks
from core.profile_analyzer import ProfileAnalyzer
from core.editor_chef import EditorChef
from core.networks.instagram.client import InstagramClient
from core.networks.instagram.discovery import InstagramDiscovery
from core.networks.twitter.client import TwitterClient
from core.networks.twitter.discovery import TwitterDiscovery
from core.networks.threads.client import ThreadsClient
from core.networks.threads.discovery import ThreadsDiscovery
from core.networks.devto.client import DevToClient
from core.networks.devto.discovery import DevToDiscovery


class AgentOrchestrator:
    def __init__(self):
        self.agent = SocialAgent()
        self.profile_analyzer = ProfileAnalyzer()
        self.editor = EditorChef()
        self.running = True

        # Platform definitions (lazy — clients are created per cycle)
        self.platform_configs = [
            {
                "name": "Instagram",
                "platform": "instagram",
                "client_class": InstagramClient,
                "discovery_class": InstagramDiscovery,
            },
            {
                "name": "Twitter",
                "platform": "twitter",
                "client_class": TwitterClient,
                "discovery_class": TwitterDiscovery,
            },
            # {
            #     "name": "Threads",
            #     "platform": "threads",
            #     "client_class": ThreadsClient,
            #     "discovery_class": ThreadsDiscovery,
            # },
            {
                "name": "Dev.to",
                "platform": "devto",
                "client_class": DevToClient,
                "discovery_class": DevToDiscovery,
            },
        ]

    def start(self):
        """Main execution loop."""
        logger.info("🤖 NetBot Orchestrator Initialized", status_code="SYSTEM")

        # Verify DB connection
        # Verify DB connection
        try:
            # Simple health check query (assuming 'posts' or similar table exists, or just check simple select)
            # Using raw sql via db interface if available, or just assume connection is alive if init worked
            # But PR asked for a real check.
            # db.supabase.table("posts").select("id").limit(1).execute() 
            # Since db wrapper might not expose table directly nicely here without import, 
            # let's assume if we can get a count it works.
            db.get_daily_count(platform="instagram") # Lightweight check
            logger.info("Connected to Supabase.")
        except Exception as e:
            logger.error(f"Failed to connect to DB: {e}. Check .env keys.")
            return

        if settings.dry_run:
            logger.warning("⚠️ MODE: DRY RUN (No comments will be posted)")

        # Loop
        while self.running:
            try:
                self.run_cycle()

                # Sleep between cycles (after all platforms are done)
                sleep_time = random.randint(settings.min_sleep_interval, settings.max_sleep_interval)
                logger.info(f"Cycle finished. Sleeping {sleep_time}s before next cycle...")
                time.sleep(sleep_time)

            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                logger.exception(f"Error in main loop: {e}", status_code="ERROR")
                time.sleep(60)

    def run_cycle(self):
        """Single execution cycle — runs each platform sequentially."""
        logger.info("--- Starting Cycle ---", status_code="SYSTEM")

        # 1. Content Curation & Personal Flow
        try:
            from scripts.fetch_news import NewsFetcher
            logger.debug("Checking for new news articles...")
            NewsFetcher().fetch_and_process()
            
            from scripts.generate_project_updates import ProjectUpdateGenerator
            logger.debug("Checking for project updates...")
            ProjectUpdateGenerator().run()
        except Exception as e:
            logger.error(f"Error in content flows: {e}")

        for cfg in self.platform_configs:
            name = cfg["name"]

            # 1. Determine requirements
            platform_value = cfg["platform"]
            
            # Interactions Limit Check
            interact_limit = settings.DAILY_LIMITS.get(platform_value, settings.daily_interaction_limit)
            current_interactions = db.get_daily_count(platform=platform_value)
            can_interact = current_interactions < interact_limit
            
            # Publications Availability Check
            can_publish = self.editor.can_publish(platform_value)
            
            logger.info(f"[{name}] Activity: Interactions({current_interactions}/{interact_limit}) | Publishing({can_publish})", status_code="FINANCE")

            if not can_interact and not can_publish:
                logger.info(f"[{name}] Limits reached for both interaction and publishing. Skipping...")
                continue

            # 2. Start browser & login
            logger.debug(f"[{name}] Starting browser (Interaction={can_interact}, Pub={can_publish})...")
            client = cfg["client_class"]()
            if not client.login():
                logger.error(f"[{name}] Failed to login. Skipping...")
                client.stop()
                continue

            # NEW: Step 3 - Content Publication (Editor Chef)
            if can_publish:
                try:
                    self.editor.transform_and_publish(client)
                except Exception as e:
                    logger.error(f"[{name}] Editor Chef failed: {e}")

            # 3. Discovery & Interaction
            if not can_interact:
                logger.info(f"[{name}] Interaction limit reached. Skipping discovery/comments.")
                client.stop()
                continue

            discovery = cfg["discovery_class"](client)
            logger.debug(f"[{name}] Discovery started...")
            limit = settings.discovery_limit
            candidates = discovery.find_candidates(limit=limit)

            if not candidates:
                logger.info(f"[{name}] No candidates found.")
                client.stop()
                continue

            # 4. Attempt Interaction
            interacted = False
            for i, post in enumerate(candidates):
                try:
                    logger.debug(f"[{name}] Analyzing Post {i+1}/{len(candidates)}: {post.id}")

                    # --- Audience Awareness (Profile Analysis) ---
                    dossier = None
                    try:
                        if hasattr(client, 'get_profile_data') and callable(client.get_profile_data):
                            logger.debug(f"[{name}] gathering dossier for @{post.author.username}...")
                            profile_data = client.get_profile_data(post.author.username)
                            if profile_data:
                                dossier = self.profile_analyzer.analyze_profile(profile_data)
                    except Exception as e:
                        logger.warning(f"[{name}] Failed to generate dossier: {e}")

                    # Agent Analysis
                    decision = self.agent.decide_and_comment(post, dossier=dossier)

                    if decision.should_act:
                        logger.info(f"[{name}] Decided to ACT (Conf: {decision.confidence_score}%): {decision.content}", stage='C', status_code='BRAIN')
                        
                        if settings.dry_run:
                             logger.info(f"[{name}] DRY RUN: Would have liked and commented.")
                             db.update_discovery_status(post.id, client.platform.value, "dry_run", f"Planned comment: {decision.content}")
                             continue

                        # Execute Action
                        try:
                            # 1. Like
                            client.like_post(post)
                            time.sleep(random.uniform(2, 4))

                            # 2. Comment
                            success = client.post_comment(post, decision.content)

                            if success:
                                # Log Interaction
                                db.log_interaction(
                                    post_id=post.id,
                                    username=post.author.username,
                                    comment_text=decision.content,
                                    platform=client.platform.value,
                                    metadata={"reasoning": decision.reasoning, "confidence": decision.confidence_score}
                                )
                                
                                # Update Discovery Status
                                db.update_discovery_status(post.id, client.platform.value, "commented", decision.reasoning)

                                # --- LIVE LEARNING (RAG) ---
                                try:
                                    content_text = f"Interaction on {client.platform.value}:\nUser: @{post.author.username}\nMy Comment: \"{decision.content}\"\nReasoning: {decision.reasoning}\nContext: {post.content}"
                                    self.agent.knowledge_base.insert(
                                        name=f"interaction_{post.id}",
                                        text_content=content_text,
                                        metadata={
                                            "post_id": post.id,
                                            "platform": client.platform.value,
                                            "username": post.author.username,
                                            "created_at": datetime.now(timezone.utc).isoformat(),
                                            "confidence": decision.confidence_score
                                        },
                                        upsert=True
                                    )
                                    logger.debug(f"[{name}] 🧠 Interaction saved to memory (RAG).")
                                except Exception as e:
                                    logger.error(f"[{name}] Failed to save to memory: {e}")

                                interacted = True
                                logger.info(f"[{name}] ✅ Interaction successful.")
                                break  # Done with this platform for this cycle (1 interaction per cycle limit typically)
                            else:
                                logger.error(f"[{name}] Failed to post comment.")
                                db.update_discovery_status(post.id, client.platform.value, "error", "Failed to post comment")
                        
                        except Exception as e:
                            logger.error(f"[{name}] Error executing action: {e}")
                            db.update_discovery_status(post.id, client.platform.value, "error", str(e))

                    else:
                        logger.info(f"[{name}] Rejected.", stage='C', status_code='BRAIN')
                        logger.info(f"Reason: {decision.reasoning}", stage='C', status_code='BRAIN')
                        db.update_discovery_status(post.id, client.platform.value, "rejected", decision.reasoning)

                except Exception as e:
                    logger.error(f"[{name}] Error processing candidate {post.id}: {e}")
                    db.update_discovery_status(post.id, client.platform.value, "error", f"Processing error: {e}")
                    continue

            if not interacted:
                logger.info(f"[{name}] Finished candidates with no interaction.")

            # 5. Close browser & Playwright for this platform
            logger.debug(f"[{name}] Closing browser...")
            client.stop()

    def stop(self, signum=None, frame=None):
        """Cleanup."""
        logger.info("Shutting down...")
        self.running = False
        BrowserManager.stop()
        sys.exit(0)


if __name__ == "__main__":
    orchestrator = AgentOrchestrator()

    signal.signal(signal.SIGINT, orchestrator.stop)
    signal.signal(signal.SIGTERM, orchestrator.stop)

    orchestrator.start()

