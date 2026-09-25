from personal_affairs.application.meeting_invite_parser import (
    merge_tmeet_meeting_details,
    parse_tencent_meeting_invite,
)


def test_parse_tencent_meeting_invite_extracts_structured_fields() -> None:
    parsed = parse_tencent_meeting_invite(
        """
某同事 邀请您参加腾讯会议
会议主题：EventFlow Q3 架构评审与交付计划
会议时间：2026-08-26 14:30-16:00 (GMT+08:00)
点击链接入会：https://meeting.tencent.com/dm/AbCdEf1234
会议号：987-654-321 密码：260824
"""
    )

    assert parsed.title == "EventFlow Q3 架构评审与交付计划"
    assert parsed.start_at == "2026-08-26T14:30:00+08:00"
    assert parsed.due_at == "2026-08-26T16:00:00+08:00"
    assert parsed.estimated_minutes == 90
    assert parsed.meeting_id == "987654321"
    assert parsed.meeting_code == "260824"
    assert parsed.join_url == "https://meeting.tencent.com/dm/AbCdEf1234"
    assert parsed.missing_fields == []
    assert "原始文本" not in parsed.notes
    assert parsed.proposed_item["status"] == "planned"
    assert parsed.proposed_item["event_format"] == "online"
    assert parsed.proposed_item["event_url"] == "https://meeting.tencent.com/dm/AbCdEf1234"


def test_parse_plain_meeting_number_as_identifier_for_cli_completion() -> None:
    parsed = parse_tencent_meeting_invite("987-654-321")

    assert parsed.meeting_id == "987654321"
    assert "title" in parsed.missing_fields
    assert "schedule" in parsed.missing_fields


def test_parse_invite_field_variants_and_chinese_date() -> None:
    parsed = parse_tencent_meeting_invite(
        """
Topic: 版本发布评审
会议开始时间：2026年9月24日 14:15～15:45
Meeting No.: 123-456-789
Passcode: Abc123
Join: https://video.example.com/rooms/abc-123?token=xyz.
"""
    )

    assert parsed.title == "版本发布评审"
    assert parsed.start_at == "2026-09-24T14:15:00+08:00"
    assert parsed.due_at == "2026-09-24T15:45:00+08:00"
    assert parsed.estimated_minutes == 90
    assert parsed.meeting_id == "123456789"
    assert parsed.meeting_code == "Abc123"
    assert parsed.join_url == "https://video.example.com/rooms/abc-123?token=xyz"


def test_parse_invalid_calendar_date_returns_no_schedule() -> None:
    parsed = parse_tencent_meeting_invite("会议时间：2026-02-31 14:00-15:00")

    assert parsed.start_at is None
    assert parsed.due_at is None
    assert parsed.estimated_minutes is None


def test_merge_tmeet_details_fills_missing_title_and_schedule() -> None:
    parsed = parse_tencent_meeting_invite("会议号：987-654-321")

    merged = merge_tmeet_meeting_details(
        parsed,
        {
            "subject": "产品例会",
            "start_time": "2026-08-26T14:30:00+08:00",
            "end_time": "2026-08-26T15:00:00+08:00",
            "join_url": "https://meeting.tencent.com/dm/AbCdEf1234",
        },
    )

    assert merged.title == "产品例会"
    assert merged.start_at == "2026-08-26T14:30:00+08:00"
    assert merged.due_at == "2026-08-26T15:00:00+08:00"
    assert merged.estimated_minutes == 30
    assert merged.join_url == "https://meeting.tencent.com/dm/AbCdEf1234"
    assert merged.missing_fields == []
