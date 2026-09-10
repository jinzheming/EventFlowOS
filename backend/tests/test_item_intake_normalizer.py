from datetime import date
from uuid import uuid4

from personal_affairs.application.item_intake_normalizer import (
    IntakeContext,
    apply_item_intake_suggestion,
)
from personal_affairs.application.item_service import _should_normalize_intake
from personal_affairs.domain.enums import ItemScope, ItemStatus, Priority


def test_apply_item_intake_suggestion_fills_inbox_fields_and_existing_links() -> None:
    project_id = uuid4()
    person_id = uuid4()
    tag_id = uuid4()
    payload = {
        "title": "明天下午三点 和小王同步 Alpha 项目 #会议",
        "scope": ItemScope.WORK,
        "status": ItemStatus.INBOX,
        "priority": Priority.NORMAL,
        "all_day": True,
        "intake_text": "明天下午三点 和小王同步 Alpha 项目 #会议",
        "intake_scope_source": "inbox",
    }
    context = IntakeContext(
        timezone="Asia/Shanghai",
        now="2026-08-26T09:00:00+08:00",
        projects=[{"id": project_id, "name": "Alpha 项目"}],
        people=[{"id": person_id, "name": "小王", "identity": "同事"}],
        tags=[{"id": tag_id, "name": "会议"}],
    )
    suggestion = {
        "title": "和小王同步 Alpha 项目",
        "scope": "work",
        "status": "planned",
        "priority": "high",
        "all_day": False,
        "start_at": "2026-08-27T15:00:00+08:00",
        "estimated_minutes": 45,
        "project_name": "Alpha 项目",
        "person_name": "小王",
        "person_role": "together",
        "tag_names": ["会议"],
        "confidence": 0.91,
    }

    normalized, meta = apply_item_intake_suggestion(
        payload,
        suggestion,
        context,
        model="deepseek:deepseek-v4-flash",
        min_confidence=0.55,
    )

    assert "intake_text" not in normalized
    assert normalized["title"] == "和小王同步 Alpha 项目"
    assert normalized["status"] == "planned"
    assert normalized["priority"] == "high"
    assert normalized["all_day"] is False
    assert normalized["start_at"].isoformat() == "2026-08-27T15:00:00+08:00"
    assert normalized["estimated_minutes"] == 45
    assert normalized["project_id"] == project_id
    assert normalized["people"] == [{"person_id": person_id, "role": "together"}]
    assert normalized["tag_ids"] == [tag_id]
    assert meta and meta["method"] == "llm_flash"
    assert "title" in meta["changed_fields"]


def test_apply_item_intake_suggestion_preserves_explicit_scope_and_schedule() -> None:
    project_id = uuid4()
    payload = {
        "title": "约牙医",
        "scope": ItemScope.PERSONAL,
        "status": ItemStatus.PLANNED,
        "priority": Priority.NORMAL,
        "all_day": True,
        "start_date": date(2026, 8, 28),
        "intake_text": "#个人 8月28日 约牙医",
        "intake_scope_source": "explicit",
    }
    context = IntakeContext(
        timezone="Asia/Shanghai",
        now="2026-08-26T09:00:00+08:00",
        projects=[{"id": project_id, "name": "工作项目"}],
        people=[],
        tags=[],
    )
    suggestion = {
        "title": "约牙医",
        "scope": "work",
        "all_day": False,
        "start_at": "2026-08-29T10:00:00+08:00",
        "project_name": "工作项目",
        "confidence": 0.95,
    }

    normalized, meta = apply_item_intake_suggestion(
        payload,
        suggestion,
        context,
        model="deepseek:deepseek-v4-flash",
        min_confidence=0.55,
    )

    assert normalized["scope"] == ItemScope.PERSONAL
    assert normalized["all_day"] is True
    assert normalized["start_date"] == date(2026, 8, 28)
    assert "project_id" not in normalized
    assert meta is None


def test_apply_item_intake_suggestion_rejects_llm_future_date_for_recent_month_day() -> None:
    payload = {
        "title": "8月27日 复盘",
        "scope": ItemScope.WORK,
        "status": ItemStatus.INBOX,
        "priority": Priority.NORMAL,
        "all_day": True,
        "intake_text": "8月27日 复盘",
        "intake_origin": "agent",
        "intake_normalization": "llm",
    }
    context = IntakeContext(timezone="Asia/Shanghai", now="2026-08-28T09:00:00+08:00", projects=[], people=[], tags=[])
    suggestion = {
        "title": "复盘",
        "all_day": True,
        "start_date": "2027-08-27",
        "confidence": 0.9,
    }

    normalized, meta = apply_item_intake_suggestion(
        payload,
        suggestion,
        context,
        model="deepseek:deepseek-v4-flash",
        min_confidence=0.55,
    )

    assert "start_date" not in normalized
    assert normalized["title"] == "复盘"
    assert meta and "start_date" not in meta["changed_fields"]


def test_apply_item_intake_suggestion_rejects_future_date_for_relative_past_words() -> None:
    payload = {
        "title": "昨天复盘",
        "scope": ItemScope.WORK,
        "status": ItemStatus.INBOX,
        "priority": Priority.NORMAL,
        "all_day": True,
        "intake_text": "昨天复盘",
        "intake_origin": "agent",
        "intake_normalization": "llm",
    }
    context = IntakeContext(timezone="Asia/Shanghai", now="2026-08-28T09:00:00+08:00", projects=[], people=[], tags=[])

    normalized, meta = apply_item_intake_suggestion(
        payload,
        {"title": "复盘", "all_day": True, "start_date": "2027-08-27", "confidence": 0.9},
        context,
        model="deepseek:deepseek-v4-flash",
        min_confidence=0.55,
    )

    assert "start_date" not in normalized
    assert normalized["title"] == "复盘"
    assert meta and "start_date" not in meta["changed_fields"]


def test_apply_item_intake_suggestion_allows_explicit_year_even_when_past() -> None:
    payload = {
        "title": "2025年8月27日 复盘",
        "scope": ItemScope.WORK,
        "status": ItemStatus.INBOX,
        "priority": Priority.NORMAL,
        "all_day": True,
        "intake_text": "2025年8月27日 复盘",
        "intake_origin": "agent",
        "intake_normalization": "llm",
    }
    context = IntakeContext(timezone="Asia/Shanghai", now="2026-08-28T09:00:00+08:00", projects=[], people=[], tags=[])

    normalized, meta = apply_item_intake_suggestion(
        payload,
        {"title": "复盘", "all_day": True, "start_date": "2025-08-27", "confidence": 0.9},
        context,
        model="deepseek:deepseek-v4-flash",
        min_confidence=0.55,
    )

    assert normalized["start_date"] == date(2025, 8, 27)
    assert meta and "start_date" in meta["changed_fields"]


def test_apply_item_intake_suggestion_skips_low_confidence() -> None:
    payload = {
        "title": "买牛奶",
        "scope": ItemScope.WORK,
        "status": ItemStatus.INBOX,
        "priority": Priority.NORMAL,
        "intake_text": "买牛奶",
    }
    context = IntakeContext(timezone="Asia/Shanghai", now="2026-08-26T09:00:00+08:00", projects=[], people=[], tags=[])

    normalized, meta = apply_item_intake_suggestion(
        payload,
        {"scope": "personal", "confidence": 0.3},
        context,
        model="deepseek:deepseek-v4-flash",
        min_confidence=0.55,
    )

    assert normalized == {key: value for key, value in payload.items() if not key.startswith("intake_")}
    assert meta is None


def test_intake_normalization_requires_explicit_llm_mode() -> None:
    assert _should_normalize_intake({"intake_origin": "web", "intake_normalization": "none"}) is False
    assert _should_normalize_intake({"intake_origin": "api"}) is False
    assert _should_normalize_intake({"intake_origin": "agent", "intake_normalization": "llm"}) is True
