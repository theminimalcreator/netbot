
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dashboard import DashboardGenerator
from core.notifications import TelegramNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyDashboard")

def verify():
    logger.info("Starting Dashboard Verification...")

    # 1. Generate
    gen = DashboardGenerator()
    metrics = gen.gather_metrics()
    logger.info(f"Metrics Gathered: {metrics}")

    # 2. Format
    report = gen.format_report(metrics)
    print("\n" + "="*30)
    print(report)
    print("="*30 + "\n")

    # 3. Send (Optional)
    notifier = TelegramNotifier()
    if notifier.token and notifier.chat_id:
        logger.info("Attempting to send to Telegram...")
        msg_id = notifier.send_message(report)
        logger.info(f"Message sent with ID: {msg_id}")
    else:
        logger.warning("Telegram credentials missing. Skipping send.")
        msg_id = "skipped_verification"

    # 4. Save
    logger.info("Saving to DB...")
    gen.save(metrics, report, msg_id)
    logger.info("Saved successfully.")

if __name__ == "__main__":
    verify()
