from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from personal_affairs.application.idempotency import create_request_hash, json_safe
from personal_affairs.domain.enums import ItemScope


def test_json_safe_converts_postgres_decimal_values() -> None:
    assert json_safe({"confidence": Decimal("0.9500")}) == {"confidence": 0.95}


def test_create_can_hash_original_payload_when_persisting_enriched_location(monkeypatch) -> None:
    from personal_affairs.api.schemas import ItemCreate
    from personal_affairs.application import item_service as service_module
    from personal_affairs.application.item_service import ItemService

    expected_hashes: list[str] = []
    item_id = uuid4()

    class FakeItems:
        conn = object()

        def replay_create_request(self, user_id, resource_type, request_id, request_hash):
            expected_hashes.append(request_hash)
            return "missing", None

        def create_item(self, user_id, payload):
            return {"id": item_id, **payload}

        def record_create_request(
            self, user_id, request_id, request_hash, resource_type, resource_id, snapshot
        ):
            expected_hashes.append(request_hash)

    class FakeActivity:
        def record(self, *args):
            pass

    class FakeOutbox:
        def __init__(self, conn):
            pass

        def record(self, *args):
            pass

    monkeypatch.setattr(service_module, "EventOutboxRepository", FakeOutbox)
    original_request = ItemCreate(
        title="客户会议",
        scope=ItemScope.PERSONAL,
        all_day=False,
        start_at=datetime(2026, 11, 3, 10, 0, tzinfo=UTC),
        due_at=datetime(2026, 11, 3, 11, 0, tzinfo=UTC),
        client_request_id="invite-123",
    )
    original_payload = original_request.model_dump(exclude_none=True)
    original_payload.pop("client_request_id")
    request = original_request.model_copy(
        update={"location_latitude": 31.2, "location_longitude": 121.4}
    )

    ItemService(cast(Any, FakeItems()), cast(Any, FakeActivity())).create(
        uuid4(),
        request,
        idempotency_payload=original_payload,
    )

    expected = create_request_hash(original_payload)
    assert expected_hashes == [expected, expected]
