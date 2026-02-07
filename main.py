"""
NetBot - Instagram AI Persona

Main entry point for the Instagram engagement bot.
Uses Playwright for browser automation and GPT-4o for content analysis.
"""
import time
import random
import signal
import sys
from datetime import datetime
from config.settings import settings
from core.database import db
from core.instagram_client import client
from core.discovery import discovery
from core.agent import agent
from core.logger import logger


def run_cycle():
    """Single execution cycle."""
    logger.info("--- Starting Cycle ---")

    # 1. Check Daily Limit
    current_count = db.get_daily_count()
    if current_count >= settings.daily_interaction_limit:
        logger.info(f"Daily limit reached ({current_count}/{settings.daily_interaction_limit}). Sleeping...")
        return

    # 2. Discovery (get multiple candidates)
    candidates = discovery.get_candidate_posts(limit=5)
    
    if not candidates:
        logger.info("No valid candidates found in this batch. Skipping cycle.")
        return

    logger.info(f"Discovery found {len(candidates)} potential candidates. Analyzing...")

    # Iterate through candidates until one succeeds
    interacted = False
    
    for i, candidate in enumerate(candidates):
        try:
            logger.info(f"--- Analyzing Candidate {i+1}/{len(candidates)}: {candidate['code']} ---")
            
            # 3. Agent Analysis & Decision
            action = agent.decide_and_comment(candidate)
            
            # 4. Action
            if action and action.should_comment:
                logger.info(f"Decided to comment: {action.comment_text}")
                
                # Get media ID
                media_id = candidate['media_id'] # Simplified since discovery filters valid ones
                
                # 1. Like the post first
                client.like_post(media_id)
                # Small human pause
                time.sleep(random.uniform(1, 2))
                
                # 2. Post comment
                success = client.post_comment(media_id, action.comment_text)
                
                if success:
                    # 5. Log & Persist
                    db.log_interaction(
                        post_id=media_id,
                        username=candidate['username'],
                        comment_text=action.comment_text,
                        metadata={"reasoning": action.reasoning}
                    )
                    
                    interacted = True
                    # 6. Random Sleep (Jitter) after successful action
                    sleep_time = random.randint(settings.min_sleep_interval, settings.max_sleep_interval)
                    logger.info(f"Interaction successful. Sleeping for {sleep_time} seconds ({sleep_time/60:.1f} min)...")
                    time.sleep(sleep_time)
                    break # Stop processing candidates for this cycle
                else:
                    logger.error("Failed to post comment. Trying next candidate...")
            else:
                logger.info(f"Skipped post. Reason: {action.reasoning if action else 'No action'}")
                # Continue to next candidate
        
        except Exception as e:
            logger.error(f"Error processing candidate {candidate.get('code', 'unknown')}: {e}")
            continue

    if not interacted:
        logger.info("Finished analyzing all candidates. No interaction made.")


def cleanup(signum=None, frame=None):
    """Cleanup browser on exit."""
    logger.info("Shutting down browser...")
    try:
        client.stop()
    except:
        pass
    sys.exit(0)


def main():
    logger.info("🤖 Instagram AI Persona Initialized (Playwright Mode)")
    
    # Register cleanup handler
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Verify DB connection on startup
    try:
        count = db.get_daily_count()
        logger.info(f"Connected to Supabase. Daily count: {count}")
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}. Check .env keys.")
        return

    # Start browser and login
    if not client.login():
        logger.error("Failed to login to Instagram. Exiting.")
        return

    if settings.dry_run:
        logger.warning("⚠️ MODE: DRY RUN (No comments will be posted)")

    # Main Loop
    try:
        while True:
            try:
                run_cycle()
                
                # Short sleep between cycles
                short_sleep = random.randint(60, 300)  # 1-5 mins
                logger.info(f"Cycle finished. Waiting {short_sleep}s before next check...")
                time.sleep(short_sleep)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.exception(f"Error in main loop: {e}")
                time.sleep(60)  # Prevent rapid crash loops
    finally:
        cleanup()


if __name__ == "__main__":
    main()
