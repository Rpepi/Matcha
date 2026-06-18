import os
import psycopg
from pathlib import Path
from app.log import setup_logging, get_logger

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_DIR = Path(__file__).resolve().parent


def run_migration():
    logger = get_logger(__name__)
    conn = psycopg.connect(DATABASE_URL)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255) UNIQUE NOT NULL,
            executed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()

    done = set(row[0] for row in conn.execute("SELECT filename FROM migrations").fetchall())

    files = sorted(file for file in os.listdir(MIGRATION_DIR) if file.endswith(".sql"))
    count = 0
    for file in files:
        if file in done:
            logger.info("skipping %s", file)
            continue
        sql = (MIGRATION_DIR / file).read_text()
        conn.execute(sql)
        conn.execute(
            "INSERT INTO migrations (filename) VALUES (%s)", (file,)
        )
        conn.commit()
        logger.info("applied %s", file)
        count += 1
    if count == 0:
        logger.info("Nothing to migrate.")
    else:
        logger.info("Done. %d migration(s) applied.", count)
    conn.close()

if __name__ == "__main__":
    setup_logging()
    run_migration()
