"""Item schema validation: recurrence and estimated-duration contract.

Regression: item creation must accept the "no recurrence" representation
(recurrence_freq/interval both null), which the frontend sends on every create
via recurrenceToRule(''). ItemPatch already allows null; ItemCreate must too.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from personal_affairs.api.schemas import ItemCreate, ItemPatch


def test_item_create_accepts_null_recurrence_fields() -> None:
    item = ItemCreate(title="x", scope="work", recurrence_freq=None, recurrence_interval=None)
    assert item.recurrence_freq is None
    assert item.recurrence_interval is None


def test_item_create_accepts_recurrence_interval() -> None:
    item = ItemCreate(title="x", scope="work", recurrence_freq="daily", recurrence_interval=2)
    assert item.recurrence_interval == 2


def test_item_create_accepts_estimated_minutes_optional() -> None:
    assert ItemCreate(title="x", scope="work").estimated_minutes is None
    item = ItemCreate(title="x", scope="work", estimated_minutes=90)
    assert item.estimated_minutes == 90


def test_item_create_rejects_estimated_minutes_out_of_range() -> None:
    with pytest.raises(ValidationError):
        ItemCreate(title="x", scope="work", estimated_minutes=0)
    with pytest.raises(ValidationError):
        ItemCreate(title="x", scope="work", estimated_minutes=10081)


def test_item_patch_accepts_estimated_minutes() -> None:
    patch = ItemPatch(estimated_minutes=60)
    assert patch.model_dump(exclude_unset=True)["estimated_minutes"] == 60
    patch = ItemPatch(estimated_minutes=None, tag_ids=[uuid4()])
    assert patch.estimated_minutes is None


def test_item_schema_accepts_multiple_logical_relations() -> None:
    predecessor = uuid4()
    successor = uuid4()
    item = ItemCreate(
        title="依赖事项",
        scope="work",
        predecessor_item_ids=[predecessor],
        successor_item_ids=[successor],
    )
    assert item.predecessor_item_ids == [predecessor]
    assert item.successor_item_ids == [successor]

    patch = ItemPatch(predecessor_item_ids=[], successor_item_ids=[successor])
    assert patch.predecessor_item_ids == []
    assert patch.successor_item_ids == [successor]


def test_item_schema_accepts_event_location_fields() -> None:
    item = ItemCreate(
        title="x",
        scope="work",
        event_format="online",
        event_location="会议室 A",
        event_url="https://meeting.example.com/j/123",
    )
    assert item.event_format == "online"
    patch = ItemPatch(event_format="offline", event_location="上海办公室", event_url=None)
    assert patch.model_dump(exclude_unset=True) == {
        "event_format": "offline",
        "event_location": "上海办公室",
        "event_url": None,
    }


def test_item_schema_rejects_invalid_event_format() -> None:
    with pytest.raises(ValidationError):
        ItemCreate(title="x", scope="work", event_format="phone")
