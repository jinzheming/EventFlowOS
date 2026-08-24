from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg_pool import ConnectionPool

from personal_affairs.storage.database import get_pool


@contextmanager
def unit_of_work(pool: ConnectionPool | None = None) -> Iterator[Connection]:
    resolved_pool = pool or get_pool()
    with resolved_pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
