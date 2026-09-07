from uuid import uuid4

from personal_affairs.application.item_intake_normalizer import ItemIntakeNormalizer
from personal_affairs.application.llm_profiles import (
    DEFAULT_LITELLM_AUTH_REF,
    DEFAULT_LITELLM_BASE_URL,
    llm_profile_presets,
    llm_purpose_presets,
    merge_llm_params,
    normalize_llm_binding,
    normalize_llm_profile,
)
from personal_affairs.config import Settings


def test_litellm_profile_defaults_to_runtime_gateway() -> None:
    normalized = normalize_llm_profile(
        "litellm",
        "deepseek:deepseek-v4-flash",
        capabilities={"json_object": True},
        default_params={"temperature": 0},
    )

    assert normalized["base_url"] == DEFAULT_LITELLM_BASE_URL
    assert normalized["auth_ref"] == DEFAULT_LITELLM_AUTH_REF
    assert normalized["model_name"] == "deepseek:deepseek-v4-flash"
    assert normalized["capabilities"] == {"json_object": True}
    assert normalized["default_params"] == {"temperature": 0}


def test_ollama_profile_defaults_to_no_auth_private() -> None:
    normalized = normalize_llm_profile("ollama", "qwen3:8b", privacy_tier="private")

    assert normalized["base_url"] == "http://127.0.0.1:11434/v1"
    assert normalized["auth_ref"] == "none"
    assert normalized["privacy_tier"] == "private"


def test_llm_binding_normalization_clears_global_scope_value() -> None:
    normalized = normalize_llm_binding(
        " intake_normalization ",
        "global",
        scope_value="ignored",
        override_params={" timeout_seconds ": 2},
        instructions="  使用 JSON 输出  ",
    )

    assert normalized == {
        "purpose_key": "intake_normalization",
        "scope_type": "global",
        "scope_value": None,
        "override_params": {"timeout_seconds": 2},
        "instructions": "使用 JSON 输出",
    }


def test_llm_presets_include_model_profiles_and_purposes() -> None:
    profile_keys = {preset["preset_key"] for preset in llm_profile_presets()}
    purpose_keys = {preset["purpose_key"] for preset in llm_purpose_presets()}

    assert {"litellm_deepseek_flash", "openai_compatible_custom", "ollama_local_structured"} <= profile_keys
    assert {"intake_normalization", "proposal_extract", "daily_brief"} <= purpose_keys


def test_merge_llm_params_allows_binding_overrides() -> None:
    assert merge_llm_params(
        {"temperature": 0, "timeout_seconds": 3},
        {"timeout_seconds": 1, "max_tokens": 500},
    ) == {"temperature": 0, "timeout_seconds": 1, "max_tokens": 500}


def test_unknown_llm_profile_values_are_rejected() -> None:
    for kwargs in (
        {"provider_key": "unknown", "model_name": "model"},
        {"provider_key": "litellm", "model_name": "model", "privacy_tier": "public"},
    ):
        try:
            normalize_llm_profile(**kwargs)
        except ValueError:
            pass
        else:  # pragma: no cover - assertion guard
            raise AssertionError("invalid LLM profile value was accepted")


def test_intake_runtime_prefers_user_binding_when_env_flag_is_disabled(monkeypatch) -> None:
    class FakeRepository:
        def __init__(self, conn) -> None:
            self.conn = conn

        def resolve_binding(self, user_id, purpose_key, scope_type="global", scope_value=None):
            assert purpose_key == "intake_normalization"
            return {
                "base_url": "http://llm-gateway.local/v1",
                "model_name": "custom:fast-json",
                "auth_ref": "none",
                "provider_key": "custom",
                "default_params": {"temperature": 0.2, "timeout_seconds": 4},
                "override_params": {"temperature": 0, "min_confidence": 0.8},
            }

    monkeypatch.setattr(
        "personal_affairs.application.item_intake_normalizer.LLMProfilesRepository",
        FakeRepository,
    )

    settings = Settings(intake_normalization_enabled=False, intake_normalization_api_key=None)
    runtime = ItemIntakeNormalizer(settings)._runtime_config(uuid4(), object())

    assert runtime is not None
    assert runtime.base_url == "http://llm-gateway.local/v1"
    assert runtime.model_name == "custom:fast-json"
    assert runtime.api_key is None
    assert runtime.params == {"temperature": 0}
    assert runtime.timeout_seconds == 4
    assert runtime.min_confidence == 0.8
