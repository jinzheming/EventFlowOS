import pytest

from personal_affairs.application.write_targets import (
    DEFAULT_FEISHU_BITABLE_FIELD_MAPPING,
    normalize_write_target,
    write_target_presets,
)


def test_feishu_write_target_defaults_to_bitable_mapping() -> None:
    format_key, mapping = normalize_write_target("feishu_bitable", None, {})
    assert format_key == "feishu_bitable_item_v1"
    assert mapping == DEFAULT_FEISHU_BITABLE_FIELD_MAPPING
    assert mapping["title"] == "事项名称"


def test_custom_write_target_preserves_custom_mapping() -> None:
    format_key, mapping = normalize_write_target(
        "custom",
        "custom_json_v1",
        {"title": "Name", "priority": "Priority", "ignored": "  "},
    )
    assert format_key == "custom_json_v1"
    assert mapping == {"title": "Name", "priority": "Priority"}


def test_write_target_rejects_unknown_format() -> None:
    with pytest.raises(ValueError):
        normalize_write_target("custom", "unknown", {})


def test_write_target_presets_include_feishu_and_custom() -> None:
    presets = write_target_presets()
    assert {preset["target_type"] for preset in presets} == {"feishu_bitable", "custom"}
    assert presets[0]["field_mapping"]["title"] == "事项名称"
