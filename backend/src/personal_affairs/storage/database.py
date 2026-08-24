from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from personal_affairs.config import Settings, get_settings

_pool: ConnectionPool | None = None


def get_pool(settings: Settings | None = None) -> ConnectionPool:
    global _pool
    resolved = settings or get_settings()
    if _pool is None:
        _pool = ConnectionPool(
            resolved.database_url,
            min_size=resolved.database_min_size,
            max_size=resolved.database_max_size,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection(settings: Settings | None = None) -> Iterator[Connection]:
    with get_pool(settings).connection() as conn:
        yield conn
