from pathlib import Path

import psycopg

from personal_affairs.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def run_migrations(database_url: str) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass('personal_affairs.schema_migrations') IS NOT NULL"
            )
            tracking_row = cur.fetchone()
            tracking_exists = bool(tracking_row and tracking_row[0])

            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                version = path.stem
                if tracking_exists:
                    cur.execute(
                        "SELECT 1 FROM personal_affairs.schema_migrations WHERE version = %s",
                        (version,),
                    )
                    if cur.fetchone():
                        continue

                cur.execute(path.read_text())
                cur.execute(
                    """
                    INSERT INTO personal_affairs.schema_migrations(version)
                    VALUES (%s)
                    ON CONFLICT (version) DO NOTHING
                    """,
                    (version,),
                )
                tracking_exists = True
                applied.append(path.name)
        conn.commit()
    return applied


def main() -> None:
    settings = get_settings()
    for name in run_migrations(settings.database_url):
        print(f"applied {name}")
