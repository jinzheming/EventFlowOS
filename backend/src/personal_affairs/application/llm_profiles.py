from typing import Any

DEFAULT_LITELLM_BASE_URL = "http://127.0.0.1:14000/v1"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_LITELLM_AUTH_REF = "intake_normalization_api_key"

DEFAULT_STRUCTURED_PARAMS: dict[str, Any] = {
    "temperature": 0,
    "response_format": {"type": "json_object"},
}

DEFAULT_STRUCTURED_CAPABILITIES: dict[str, bool] = {
    "chat": True,
    "json_object": True,
    "tool_use": False,
    "vision": False,
}

LLM_PROFILE_PRESETS: list[dict[str, Any]] = [
    {
        "preset_key": "litellm_deepseek_flash",
        "label": "LiteLLM DeepSeek Flash",
        "provider_key": "litellm",
        "base_url": DEFAULT_LITELLM_BASE_URL,
        "model_name": "deepseek:deepseek-v4-flash",
        "auth_ref": DEFAULT_LITELLM_AUTH_REF,
        "capabilities": DEFAULT_STRUCTURED_CAPABILITIES,
        "default_params": DEFAULT_STRUCTURED_PARAMS,
        "privacy_tier": "standard",
        "description": "默认快速结构化模型，适合事项录入归一化和低延迟 JSON 输出。",
    },
    {
        "preset_key": "openai_compatible_custom",
        "label": "OpenAI-compatible 自定义",
        "provider_key": "openai_compatible",
        "base_url": DEFAULT_LITELLM_BASE_URL,
        "model_name": "custom:model",
        "auth_ref": DEFAULT_LITELLM_AUTH_REF,
        "capabilities": DEFAULT_STRUCTURED_CAPABILITIES,
        "default_params": DEFAULT_STRUCTURED_PARAMS,
        "privacy_tier": "standard",
        "description": "连接任意 OpenAI-compatible 网关，用户可覆盖 base URL、模型名和参数。",
    },
    {
        "preset_key": "ollama_local_structured",
        "label": "Ollama 本地模型",
        "provider_key": "ollama",
        "base_url": DEFAULT_OLLAMA_BASE_URL,
        "model_name": "qwen3:8b",
        "auth_ref": "none",
        "capabilities": DEFAULT_STRUCTURED_CAPABILITIES,
        "default_params": DEFAULT_STRUCTURED_PARAMS,
        "privacy_tier": "private",
        "description": "本地 OpenAI-compatible 模型预设，适合不希望外发文本的场景。",
    },
]

LLM_PURPOSE_PRESETS: list[dict[str, Any]] = [
    {
        "purpose_key": "intake_normalization",
        "label": "事项录入归一化",
        "required_capabilities": ["chat", "json_object"],
        "description": "把快速录入文本归一化为标题、时间、项目、人员、标签等结构化字段。",
    },
    {
        "purpose_key": "proposal_extract",
        "label": "Agent 提议抽取",
        "required_capabilities": ["chat", "json_object"],
        "description": "从 IM、邮件、会议文本等来源抽取待审批事项提议。",
    },
    {
        "purpose_key": "daily_brief",
        "label": "今日简报",
        "required_capabilities": ["chat"],
        "description": "生成今日计划、提醒和风险摘要。",
    },
    {
        "purpose_key": "meeting_parse",
        "label": "会议解析",
        "required_capabilities": ["chat", "json_object"],
        "description": "解析会议邀约、纪要和 action items。",
    },
    {
        "purpose_key": "external_formatting",
        "label": "外部写入格式化",
        "required_capabilities": ["chat", "json_object"],
        "description": "按外部绑定的字段映射和格式要求组织写入 payload。",
    },
    {
        "purpose_key": "risk_review",
        "label": "高风险变更复核",
        "required_capabilities": ["chat", "json_object"],
        "description": "在批量修改、冲突日程或重要事项变更前生成风险判断。",
    },
]

SUPPORTED_LLM_PROVIDER_KEYS = {"litellm", "openai_compatible", "ollama", "custom"}
SUPPORTED_LLM_SCOPE_TYPES = {"global", "project", "source_type", "item_type", "risk_tier"}
SUPPORTED_LLM_PRIVACY_TIERS = {"standard", "private", "sensitive"}


def _normalize_object(value: dict[str, Any] | None, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return {str(key).strip(): item for key, item in value.items() if str(key).strip()}


def normalize_llm_profile(
    provider_key: str,
    model_name: str,
    *,
    preset_key: str | None = None,
    base_url: str | None = None,
    auth_ref: str | None = None,
    capabilities: dict[str, Any] | None = None,
    default_params: dict[str, Any] | None = None,
    privacy_tier: str = "standard",
) -> dict[str, Any]:
    provider = str(provider_key).strip() or "litellm"
    if provider not in SUPPORTED_LLM_PROVIDER_KEYS:
        raise ValueError(f"unsupported provider_key: {provider}")

    model = str(model_name).strip()
    if not model:
        raise ValueError("model_name cannot be blank")

    resolved_base_url = str(base_url or "").strip() or None
    if resolved_base_url is None and provider in {"litellm", "openai_compatible"}:
        resolved_base_url = DEFAULT_LITELLM_BASE_URL
    elif resolved_base_url is None and provider == "ollama":
        resolved_base_url = DEFAULT_OLLAMA_BASE_URL

    resolved_auth_ref = str(auth_ref or "").strip() or None
    if resolved_auth_ref is None and provider in {"litellm", "openai_compatible", "custom"}:
        resolved_auth_ref = DEFAULT_LITELLM_AUTH_REF
    elif provider == "ollama" and resolved_auth_ref is None:
        resolved_auth_ref = "none"

    resolved_privacy_tier = str(privacy_tier or "standard").strip() or "standard"
    if resolved_privacy_tier not in SUPPORTED_LLM_PRIVACY_TIERS:
        raise ValueError(f"unsupported privacy_tier: {resolved_privacy_tier}")

    return {
        "provider_key": provider,
        "preset_key": str(preset_key).strip() if preset_key else None,
        "base_url": resolved_base_url,
        "model_name": model,
        "auth_ref": resolved_auth_ref,
        "capabilities": _normalize_object(capabilities, "capabilities"),
        "default_params": _normalize_object(default_params, "default_params"),
        "privacy_tier": resolved_privacy_tier,
    }


def normalize_llm_binding(
    purpose_key: str,
    scope_type: str,
    *,
    scope_value: str | None = None,
    override_params: dict[str, Any] | None = None,
    instructions: str | None = None,
) -> dict[str, Any]:
    purpose = str(purpose_key).strip()
    if not purpose:
        raise ValueError("purpose_key cannot be blank")
    scope = str(scope_type or "global").strip() or "global"
    if scope not in SUPPORTED_LLM_SCOPE_TYPES:
        raise ValueError(f"unsupported scope_type: {scope}")
    resolved_scope_value = str(scope_value or "").strip() or None
    if scope == "global":
        resolved_scope_value = None
    return {
        "purpose_key": purpose,
        "scope_type": scope,
        "scope_value": resolved_scope_value,
        "override_params": _normalize_object(override_params, "override_params"),
        "instructions": str(instructions or "").strip() or None,
    }


def merge_llm_params(default_params: dict[str, Any] | None, override_params: dict[str, Any] | None) -> dict[str, Any]:
    return {**(default_params or {}), **(override_params or {})}


def llm_profile_presets() -> list[dict[str, Any]]:
    return [dict(preset) for preset in LLM_PROFILE_PRESETS]


def llm_purpose_presets() -> list[dict[str, Any]]:
    return [dict(preset) for preset in LLM_PURPOSE_PRESETS]
