from pathlib import Path

import psycopg

from personal_affairs.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


def run_migrations(database_url: str) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cur.execute(path.read_text())
                applied.append(path.name)
        conn.commit()
    return applied


def main() -> None:
    settings = get_settings()
    for name in run_migrations(settings.database_url):
        print(f"applied {name}")
