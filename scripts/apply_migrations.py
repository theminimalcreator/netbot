import os
import sys
import logging
import psycopg
from urllib.parse import urlparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Migration")

def apply_migrations():
    """
    Applies .sql files from the migrations/ directory to the database.
    """
    db_url = settings.PG_DATABASE_URL
    if not db_url:
        logger.error("PG_DATABASE_URL is not set in .env")
        return

    migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
    if not os.path.exists(migrations_dir):
        logger.error(f"Migrations directory not found: {migrations_dir}")
        return

    try:
        # Use psycopg v3 (pip install psycopg)
        # Connect using context manager to ensure close
        with psycopg.connect(db_url) as conn:
            # Get list of sql files
            files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
            
            for file in files:
                logger.info(f"Applying {file}...")
                file_path = os.path.join(migrations_dir, file)
                with open(file_path, "r") as f:
                    sql = f.read()
                
                try:
                    # Execute each file in its own transaction
                    with conn.transaction():
                         conn.execute(sql)
                    logger.info(f"✅ Applied {file}")
                except Exception as e:
                    # Transaction is rolled back automatically on exception exit from context
                    logger.warning(f"⚠️  Error applying {file} (might already exist or failed): {e}")

        logger.info("🎉 All migrations processed.")

    except Exception as e:
        logger.error(f"Database connection failed: {e}")

if __name__ == "__main__":
    apply_migrations()
