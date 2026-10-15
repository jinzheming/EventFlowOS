from typing import Any

DEFAULT_FEISHU_BITABLE_FIELD_MAPPING: dict[str, str] = {
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

WRITE_TARGET_PRESETS: list[dict[str, Any]] = [
    {
        "target_type": "feishu_bitable",
        "label": "飞书多维表格",
        "format_key": "feishu_bitable_item_v1",
        "field_mapping": DEFAULT_FEISHU_BITABLE_FIELD_MAPPING,
        "description": "以事项字段为基础生成可写入飞书 Base 的记录；字段名可按用户自己的表格列名调整。",
    },
    {
        "target_type": "custom",
        "label": "自定义目标",
        "format_key": "custom_json_v1",
        "field_mapping": {},
        "description": "保留链接、格式键、字段映射和说明，供 Agent 或外部自动化按用户规则处理。",
    },
]

SUPPORTED_TARGET_TYPES = {"feishu_bitable", "custom"}
SUPPORTED_FORMAT_KEYS = {"feishu_bitable_item_v1", "compact_item_v1", "custom_json_v1"}


def normalize_write_target(
    target_type: str,
    format_key: str | None,
    field_mapping: dict[str, Any] | None,
) -> tuple[str, dict[str, str]]:
    if target_type not in SUPPORTED_TARGET_TYPES:
        raise ValueError(f"unsupported target_type: {target_type}")

    resolved_format = format_key or (
        "feishu_bitable_item_v1" if target_type == "feishu_bitable" else "custom_json_v1"
    )
    if resolved_format not in SUPPORTED_FORMAT_KEYS:
        raise ValueError(f"unsupported format_key: {resolved_format}")

    mapping = field_mapping or {}
    if target_type == "feishu_bitable" and not mapping:
        mapping = DEFAULT_FEISHU_BITABLE_FIELD_MAPPING
    if not isinstance(mapping, dict):
        raise ValueError("field_mapping must be an object")

    normalized: dict[str, str] = {}
    for source_key, target_field in mapping.items():
        source = str(source_key).strip()
        target = str(target_field).strip()
        if source and target:
            normalized[source] = target
    return resolved_format, normalized


def write_target_presets() -> list[dict[str, Any]]:
    return [dict(preset) for preset in WRITE_TARGET_PRESETS]
