from uuid import uuid4

import pytest

from personal_affairs.domain.errors import DomainError, ErrorCode
from personal_affairs.domain.policies import validate_tag_parent


def _tag(tag_id, parent_id=None):
    return {"id": tag_id, "name": "x", "color": "#123456", "parent_id": parent_id}


def test_tag_parent_must_exist() -> None:
    with pytest.raises(DomainError) as raised:
        validate_tag_parent(None, uuid4(), None, None, False)
    assert raised.value.code == ErrorCode.TAG_INVALID_PARENT


def test_tag_parent_must_be_top_level() -> None:
    parent_id = uuid4()
    child_parent = _tag(parent_id, parent_id=uuid4())
    with pytest.raises(DomainError) as raised:
        validate_tag_parent(None, parent_id, child_parent, None, False)
    assert raised.value.code == ErrorCode.TAG_DEPTH_EXCEEDED


def test_tag_cannot_be_its_own_parent() -> None:
    tag_id = uuid4()
    with pytest.raises(DomainError) as raised:
        validate_tag_parent(tag_id, tag_id, _tag(tag_id), None, False)
    assert raised.value.code == ErrorCode.TAG_INVALID_PARENT


def test_top_level_tag_with_children_cannot_be_demoted() -> None:
    tag_id = uuid4()
    parent_id = uuid4()
    current = _tag(tag_id, parent_id=None)
    with pytest.raises(DomainError) as raised:
        validate_tag_parent(tag_id, parent_id, _tag(parent_id), current, has_children=True)
    assert raised.value.code == ErrorCode.TAG_DEPTH_EXCEEDED


def test_child_can_move_between_top_level_parents() -> None:
    tag_id = uuid4()
    parent_id = uuid4()
    current = _tag(tag_id, parent_id=uuid4())
    validate_tag_parent(tag_id, parent_id, _tag(parent_id), current, has_children=False)


def test_create_under_top_level_parent_is_valid() -> None:
    parent_id = uuid4()
    validate_tag_parent(None, parent_id, _tag(parent_id), None, False)
