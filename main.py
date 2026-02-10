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
nest_asyncio.apply()

from config.settings import settings
from core.database import db
from core.agent import SocialAgent
from core.logger import logger
from core.browser_manager import BrowserManager

# Networks
from core.profile_analyzer import ProfileAnalyzer
from core.networks.instagram.client import InstagramClient
from core.networks.instagram.discovery import InstagramDiscovery
from core.networks.twitter.client import TwitterClient
from core.networks.twitter.discovery import TwitterDiscovery
from core.networks.threads.client import ThreadsClient
from core.networks.threads.discovery import ThreadsDiscovery


class AgentOrchestrator:
    def __init__(self):
        self.agent = SocialAgent()
        self.profile_analyzer = ProfileAnalyzer()
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
            {
                "name": "Threads",
                "platform": "threads",
                "client_class": ThreadsClient,
                "discovery_class": ThreadsDiscovery,
            },
        ]

    def start(self):
        """Main execution loop."""
        logger.info("🤖 NetBot Orchestrator Initialized")

        # Verify DB connection
        try:
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
                logger.exception(f"Error in main loop: {e}")
                time.sleep(60)

    def run_cycle(self):
        """Single execution cycle — runs each platform sequentially."""
        logger.info("--- Starting Cycle ---")

        for cfg in self.platform_configs:
            name = cfg["name"]

            # 1. Check daily limit BEFORE starting the browser
            platform_value = cfg["platform"]
            limit = settings.DAILY_LIMITS.get(platform_value, settings.daily_interaction_limit)
            current_count = db.get_daily_count(platform=platform_value)
            logger.info(f"[{name}] Daily interactions: {current_count}/{limit}")

            if current_count >= limit:
                logger.info(f"[{name}] Daily limit reached. Skipping...")
                continue

            # 2. Start browser & login
            logger.info(f"[{name}] Starting browser...")
            client = cfg["client_class"]()
            if not client.login():
                logger.error(f"[{name}] Failed to login. Skipping...")
                client.stop()
                BrowserManager.stop()
                continue

            # 3. Discovery
            discovery = cfg["discovery_class"](client)
            logger.info(f"[{name}] Discovery started...")
            candidates = discovery.find_candidates(limit=5)

            if not candidates:
                logger.info(f"[{name}] No candidates found.")
                client.stop()
                BrowserManager.stop()
                continue

            # 4. Attempt Interaction
            interacted = False
            for i, post in enumerate(candidates):
                try:
                    logger.info(f"[{name}] Analyzing Post {i+1}/{len(candidates)}: {post.id}")

                    # --- Audience Awareness (Profile Analysis) ---
                    dossier = None
                    try:
                        if hasattr(client, 'get_profile_data') and client.get_profile_data:
                            logger.info(f"[{name}] gathering dossier for @{post.author.username}...")
                            profile_data = client.get_profile_data(post.author.username)
                            if profile_data:
                                dossier = self.profile_analyzer.analyze_profile(profile_data)
                    except Exception as e:
                        logger.warning(f"[{name}] Failed to generate dossier: {e}")

                    # Agent Analysis
                    decision = self.agent.decide_and_comment(post, dossier=dossier)

                    if decision.should_act:
                        logger.info(f"[{name}] Decided to ACT: {decision.content}")

                        # Execute Action
                        client.like_post(post)
                        time.sleep(random.uniform(1, 2))

                        success = client.post_comment(post, decision.content)

                        if success:
                            # Log
                            db.log_interaction(
                                post_id=post.id,
                                username=post.author.username,
                                comment_text=decision.content,
                                platform=client.platform.value,
                                metadata={"reasoning": decision.reasoning}
                            )

                            # --- LIVE LEARNING (RAG) ---
                            try:
                                content_text = f"Interaction on {client.platform.value}:\nUser: @{post.author.username}\nMy Comment: \"{decision.content}\"\nReasoning: {decision.reasoning}"
                                self.agent.knowledge_base.insert(
                                    name=f"interaction_{post.id}",
                                    text_content=content_text,
                                    metadata={
                                        "post_id": post.id,
                                        "platform": client.platform.value,
                                        "username": post.author.username,
                                        "created_at": "now"
                                    },
                                    upsert=True
                                )
                                logger.info(f"[{name}] 🧠 Interaction saved to memory (RAG).")
                            except Exception as e:
                                logger.error(f"[{name}] Failed to save to memory: {e}")

                            interacted = True
                            logger.info(f"[{name}] ✅ Interaction successful.")
                            break  # Done with this platform
                        else:
                            logger.error(f"[{name}] Failed to execute action.")
                    else:
                        logger.info(f"[{name}] Skipped. Reason: {decision.reasoning}")

                except Exception as e:
                    logger.error(f"[{name}] Error processing candidate {post.id}: {e}")
                    continue

            if not interacted:
                logger.info(f"[{name}] Finished candidates with no interaction.")

            # 5. Close browser & Playwright for this platform
            logger.info(f"[{name}] Closing browser...")
            client.stop()
            BrowserManager.stop()

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

