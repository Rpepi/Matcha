import os
import sys
import psycopg
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATION_DIR = Path(__file__).resolve().parent


def run_migration():
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
            print(f"skipping {file}")
            continue
        sql = (MIGRATION_DIR / file).read_text()
        conn.execute(sql)
        conn.execute(
            "INSERT INTO migrations (filename) VALUES (%s)", (file,)
        )
        conn.commit()
        print(f"✅ {file}")
        count +=1
    if count == 0:
        print("Nothing to migrate.")
    else:
        print(f"Done . {count} migrations applied.")
    conn.close()

if __name__ == "__main__":
    run_migration()