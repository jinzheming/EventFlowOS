from personal_affairs.application.external_profiles import (
    DEFAULT_ITEM_WRITE_FIELD_MAPPING,
    external_profile_presets,
    external_purpose_presets,
    normalize_external_binding,
    normalize_external_profile,
)


def test_external_profile_defaults_auth_ref() -> None:
    normalized = normalize_external_profile("feishu", "write", preset_key="feishu_bitable", auth_ref=None)

    assert normalized == {
        "provider_key": "feishu",
        "capability": "write",
        "preset_key": "feishu_bitable",
        "auth_ref": "runtime_external",
    }


def test_feishu_item_write_binding_defaults_mapping() -> None:
    normalized = normalize_external_binding(
        "item_write",
        "global",
        "https://feishu.example/base",
        "feishu_bitable_item_v1",
        field_mapping={},
        conflict_policy="append",
    )

    assert normalized["scope_value"] is None
    assert normalized["field_mapping"] == DEFAULT_ITEM_WRITE_FIELD_MAPPING
    assert normalized["value_mapping"] == {}
    assert normalized["conflict_policy"] == "append"


def test_custom_binding_preserves_mapping_and_scope() -> None:
    normalized = normalize_external_binding(
        "calendar_sync",
        "project",
        "calendar-id",
        "calendar_event_v1",
        scope_value="project-1",
        field_mapping={" title ": "summary"},
        value_mapping={"status": {"done": "completed"}},
        instructions="  只同步定时事项  ",
    )

    assert normalized["scope_type"] == "project"
    assert normalized["scope_value"] == "project-1"
    assert normalized["field_mapping"] == {"title": "summary"}
    assert normalized["value_mapping"] == {"status": {"done": "completed"}}
    assert normalized["instructions"] == "只同步定时事项"


def test_external_presets_include_common_capabilities() -> None:
    provider_keys = {preset["provider_key"] for preset in external_profile_presets()}
    purpose_keys = {preset["purpose_key"] for preset in external_purpose_presets()}

    assert {"feishu", "webhook", "calendar", "custom_http"} <= provider_keys
    assert {"item_write", "calendar_sync", "reminder_notify", "source_import"} <= purpose_keys


def test_invalid_external_values_are_rejected() -> None:
    invalid_calls = [
        lambda: normalize_external_profile("unknown", "write"),
        lambda: normalize_external_profile("feishu", "unknown"),
        lambda: normalize_external_binding("item_write", "bad_scope", "target", "custom_json_v1"),
        lambda: normalize_external_binding("item_write", "global", "", "custom_json_v1"),
        lambda: normalize_external_binding("item_write", "global", "target", "unknown_format"),
        lambda: normalize_external_binding("item_write", "global", "target", "custom_json_v1", conflict_policy="overwrite"),
    ]

    for call in invalid_calls:
        try:
            call()
        except ValueError:
            pass
        else:  # pragma: no cover - assertion guard
            raise AssertionError("invalid external profile/binding value was accepted")
