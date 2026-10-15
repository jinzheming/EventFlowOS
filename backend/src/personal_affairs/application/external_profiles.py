from typing import Any

DEFAULT_ITEM_WRITE_FIELD_MAPPING: dict[str, str] = {
    "title": "事项名称",
    "scope": "范围",
    "status": "状态",
    "priority": "优先级",
    "schedule": "时间",
    "project_name": "项目",
    "notes": "备注",
    "event_type": "事件",
    "source_id": "来源ID",
    "updated_at": "更新时间",
}

DEFAULT_CALENDAR_FIELD_MAPPING: dict[str, str] = {
    "title": "title",
    "start_at": "start",
    "due_at": "end",
    "location": "location",
    "notes": "description",
    "attendees": "attendees",
}

DEFAULT_NOTIFY_FIELD_MAPPING: dict[str, str] = {
    "title": "title",
    "message": "text",
    "item_id": "source_id",
    "event_type": "event_type",
}

EXTERNAL_PROFILE_PRESETS: list[dict[str, Any]] = [
    {
        "preset_key": "feishu_bitable",
        "label": "飞书多维表格",
        "provider_key": "feishu",
        "capability": "write",
        "auth_ref": "runtime_external",
        "default_format_key": "feishu_bitable_item_v1",
        "default_field_mapping": DEFAULT_ITEM_WRITE_FIELD_MAPPING,
        "description": "把事项写入飞书 Base；表链接、字段映射和写入说明均可由用户覆盖。",
    },
    {
        "preset_key": "custom_http_json",
        "label": "自定义 HTTP JSON",
        "provider_key": "custom_http",
        "capability": "write",
        "auth_ref": "runtime_external",
        "default_format_key": "custom_json_v1",
        "default_field_mapping": {},
        "description": "把事项、通知或同步 payload 发给自定义 HTTP endpoint。",
    },
    {
        "preset_key": "webhook_notify",
        "label": "Webhook 通知",
        "provider_key": "webhook",
        "capability": "notify",
        "auth_ref": "runtime_external",
        "default_format_key": "webhook_notification_v1",
        "default_field_mapping": DEFAULT_NOTIFY_FIELD_MAPPING,
        "description": "把提醒、事项完成等事件投递到 n8n、activepieces 或自写 Webhook。",
    },
    {
        "preset_key": "calendar_sync",
        "label": "外部日历同步",
        "provider_key": "calendar",
        "capability": "sync",
        "auth_ref": "runtime_external",
        "default_format_key": "calendar_event_v1",
        "default_field_mapping": DEFAULT_CALENDAR_FIELD_MAPPING,
        "description": "把定时事项同步为外部日历事件；后续 adapter 可接 CalDAV/Google/Microsoft。",
    },
]

EXTERNAL_PURPOSE_PRESETS: list[dict[str, Any]] = [
    {
        "purpose_key": "item_write",
        "label": "事项写入",
        "capabilities": ["write"],
        "description": "把 Personal Affairs 事项写入外部表格、数据库或自定义 endpoint。",
    },
    {
        "purpose_key": "calendar_sync",
        "label": "日历同步",
        "capabilities": ["sync"],
        "description": "把有时间的工作/个人事项同步到外部日历。",
    },
    {
        "purpose_key": "reminder_notify",
        "label": "提醒通知",
        "capabilities": ["notify"],
        "description": "把提醒触发、确认、失败等事件投递到外部通知渠道。",
    },
    {
        "purpose_key": "source_import",
        "label": "外部来源导入",
        "capabilities": ["read"],
        "description": "从 IM、邮箱、文档、剪贴板或个人知识库导入事项候选。",
    },
    {
        "purpose_key": "lookup",
        "label": "外部查询",
        "capabilities": ["lookup"],
        "description": "查询外部联系人、地点、项目、标签或状态字典。",
    },
]

SUPPORTED_EXTERNAL_PROVIDER_KEYS = {"feishu", "webhook", "notion", "calendar", "custom_http"}
SUPPORTED_EXTERNAL_CAPABILITIES = {"write", "read", "sync", "notify", "lookup", "export"}
SUPPORTED_EXTERNAL_SCOPE_TYPES = {"global", "project", "item_type", "source_type", "person", "tag"}
SUPPORTED_EXTERNAL_CONFLICT_POLICIES = {"append", "update", "skip", "ask"}
SUPPORTED_EXTERNAL_FORMAT_KEYS = {
    "feishu_bitable_item_v1",
    "custom_json_v1",
    "webhook_notification_v1",
    "calendar_event_v1",
    "notion_database_item_v1",
}


def _normalize_object(value: dict[str, Any] | None, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return {str(key).strip(): item for key, item in value.items() if str(key).strip()}


def normalize_external_profile(
    provider_key: str,
    capability: str,
    *,
    preset_key: str | None = None,
    auth_ref: str | None = None,
) -> dict[str, Any]:
    provider = str(provider_key).strip()
    if provider not in SUPPORTED_EXTERNAL_PROVIDER_KEYS:
        raise ValueError(f"unsupported provider_key: {provider}")
    resolved_capability = str(capability).strip()
    if resolved_capability not in SUPPORTED_EXTERNAL_CAPABILITIES:
        raise ValueError(f"unsupported capability: {resolved_capability}")
    return {
        "provider_key": provider,
        "capability": resolved_capability,
        "preset_key": str(preset_key).strip() if preset_key else None,
        "auth_ref": str(auth_ref or "").strip() or "runtime_external",
    }


def normalize_external_binding(
    purpose_key: str,
    scope_type: str,
    target_ref: str,
    format_key: str,
    *,
    scope_value: str | None = None,
    field_mapping: dict[str, Any] | None = None,
    value_mapping: dict[str, Any] | None = None,
    instructions: str | None = None,
    conflict_policy: str = "ask",
) -> dict[str, Any]:
    purpose = str(purpose_key).strip()
    if not purpose:
        raise ValueError("purpose_key cannot be blank")

    scope = str(scope_type or "global").strip() or "global"
    if scope not in SUPPORTED_EXTERNAL_SCOPE_TYPES:
        raise ValueError(f"unsupported scope_type: {scope}")
    resolved_scope_value = str(scope_value or "").strip() or None
    if scope == "global":
        resolved_scope_value = None

    target = str(target_ref).strip()
    if not target:
        raise ValueError("target_ref cannot be blank")

    fmt = str(format_key).strip()
    if fmt not in SUPPORTED_EXTERNAL_FORMAT_KEYS:
        raise ValueError(f"unsupported format_key: {fmt}")

    policy = str(conflict_policy or "ask").strip() or "ask"
    if policy not in SUPPORTED_EXTERNAL_CONFLICT_POLICIES:
        raise ValueError(f"unsupported conflict_policy: {policy}")

    normalized_field_mapping = _normalize_object(field_mapping, "field_mapping")
    if fmt == "feishu_bitable_item_v1" and not normalized_field_mapping:
        normalized_field_mapping = dict(DEFAULT_ITEM_WRITE_FIELD_MAPPING)

    return {
        "purpose_key": purpose,
        "scope_type": scope,
        "scope_value": resolved_scope_value,
        "target_ref": target,
        "format_key": fmt,
        "field_mapping": normalized_field_mapping,
        "value_mapping": _normalize_object(value_mapping, "value_mapping"),
        "instructions": str(instructions or "").strip() or None,
        "conflict_policy": policy,
    }


def external_profile_presets() -> list[dict[str, Any]]:
    return [dict(preset) for preset in EXTERNAL_PROFILE_PRESETS]


def external_purpose_presets() -> list[dict[str, Any]]:
    return [dict(preset) for preset in EXTERNAL_PURPOSE_PRESETS]
