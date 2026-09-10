from dataclasses import dataclass
from uuid import uuid4

from personal_affairs.domain.enums import ItemScope
from personal_affairs.storage.repositories.items import ItemsRepository


@dataclass
class QueryCall:
    query: str
    params: list[object]


class RecordingCursor:
    def __init__(self, total: int | None = None) -> None:
        self.total = total

    def fetchone(self) -> dict | None:
        if self.total is None:
            return None
        return {"total": self.total}

    def fetchall(self) -> list[dict]:
        return []


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[QueryCall] = []

    def execute(self, query: str, params: list[object]):
        self.calls.append(QueryCall(query=query, params=list(params)))
        return RecordingCursor(total=0 if "COUNT(*) AS total" in query else None)


def test_list_history_items_done_uses_completion_sort_and_offset() -> None:
    conn = RecordingConnection()

    rows, total = ItemsRepository(conn).list_history_items(uuid4(), ItemScope.WORK, "done", limit=30, offset=60)

    assert rows == []
    assert total == 0
    assert len(conn.calls) == 2
    count_call, list_call = conn.calls
    assert "i.archived_at IS NULL" in count_call.query
    assert "i.status = %s" in count_call.query
    assert "COALESCE(i.completed_at, i.updated_at) DESC" in list_call.query
    assert list_call.params[-2:] == [30, 60]


def test_list_history_items_archived_uses_archive_fallback_and_rich_search() -> None:
    conn = RecordingConnection()

    ItemsRepository(conn).list_history_items(uuid4(), ItemScope.PERSONAL, "archived", limit=25, offset=0, search="alpha")

    count_call, list_call = conn.calls
    assert "i.archived_at IS NOT NULL" in count_call.query
    assert "CASE WHEN i.status = 'done'" in list_call.query
    assert "personal_affairs.item_tags" in count_call.query
    assert "personal_affairs.item_people" in count_call.query
    assert "i.event_location ILIKE" in count_call.query
    assert "i.event_url ILIKE" in count_call.query
    assert count_call.params.count("%alpha%") == 9
