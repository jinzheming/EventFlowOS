import json
from base64 import b64encode
from hashlib import sha256

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi.testclient import TestClient

from personal_affairs.config import Settings, get_settings


def test_feishu_challenge_does_not_require_database(monkeypatch) -> None:
    monkeypatch.setenv("PERSONAL_AFFAIRS_APP_ENV", "unit")
    monkeypatch.setenv("PERSONAL_AFFAIRS_FEISHU_IM_VERIFICATION_TOKEN", "secret")
    get_settings.cache_clear()

    from personal_affairs.api.app import create_app
    from personal_affairs.api.routes import integrations_feishu

    def fail_pool(*args, **kwargs):
        raise AssertionError("challenge should not open a database connection")

    monkeypatch.setattr(integrations_feishu, "get_pool", fail_pool)
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/integrations/feishu/im/events",
            json={"type": "url_verification", "token": "secret", "challenge": "ok"},
        )

    assert response.status_code == 200
    assert response.json() == {"challenge": "ok"}


def test_feishu_challenge_requires_configured_token(monkeypatch) -> None:
    monkeypatch.setenv("PERSONAL_AFFAIRS_APP_ENV", "unit")
    monkeypatch.setenv("PERSONAL_AFFAIRS_FEISHU_IM_VERIFICATION_TOKEN", "secret")
    get_settings.cache_clear()

    from personal_affairs.api.app import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/integrations/feishu/im/events",
            json={"type": "url_verification", "challenge": "ok"},
        )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_feishu_encrypted_challenge_does_not_require_database(monkeypatch) -> None:
    monkeypatch.setenv("PERSONAL_AFFAIRS_APP_ENV", "unit")
    monkeypatch.setenv("PERSONAL_AFFAIRS_FEISHU_IM_VERIFICATION_TOKEN", "secret")
    monkeypatch.setenv("PERSONAL_AFFAIRS_FEISHU_IM_ENCRYPT_KEY", "encrypt-key")
    get_settings.cache_clear()

    from personal_affairs.api.app import create_app
    from personal_affairs.api.routes import integrations_feishu

    def fail_pool(*args, **kwargs):
        raise AssertionError("challenge should not open a database connection")

    monkeypatch.setattr(integrations_feishu, "get_pool", fail_pool)
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/integrations/feishu/im/events",
            json={"encrypt": _encrypt_feishu_payload({"type": "url_verification", "token": "secret", "challenge": "ok"}, "encrypt-key")},
        )

    assert response.status_code == 200
    assert response.json() == {"challenge": "ok"}


def test_feishu_signature_uses_raw_body_with_encrypt_key() -> None:
    from personal_affairs.api.routes.integrations_feishu import _verify_signature

    body = b'{"event":{"message":{"content":"{}"}}}'
    cfg = Settings(feishu_im_encrypt_key="encrypt-key")
    signature = sha256(b"1700000000nonceencrypt-key" + body).hexdigest()

    _verify_signature(body, cfg, "1700000000", "nonce", signature)


def test_feishu_disabled_event_returns_not_found_without_database(monkeypatch) -> None:
    monkeypatch.setenv("PERSONAL_AFFAIRS_APP_ENV", "unit")
    monkeypatch.setenv("PERSONAL_AFFAIRS_FEISHU_IM_ENABLED", "false")
    monkeypatch.delenv("PERSONAL_AFFAIRS_FEISHU_IM_VERIFICATION_TOKEN", raising=False)
    get_settings.cache_clear()

    from personal_affairs.api.app import create_app
    from personal_affairs.api.routes import integrations_feishu

    def fail_pool(*args, **kwargs):
        raise AssertionError("disabled integration should not open a database connection")

    monkeypatch.setattr(integrations_feishu, "get_pool", fail_pool)
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/integrations/feishu/im/events",
            json={
                "header": {"event_id": "evt_1", "tenant_key": "tenant"},
                "event": {"message": {"message_type": "text", "message_id": "msg_1", "content": "{\"text\":\"hi\"}"}},
            },
        )

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_extract_feishu_text_message_accepts_string_content() -> None:
    from personal_affairs.api.routes.integrations_feishu import extract_feishu_text_message

    message = extract_feishu_text_message(
        {
            "header": {"event_id": "evt_1", "tenant_key": "tenant"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_1"}},
                "message": {
                    "chat_id": "oc_1",
                    "message_id": "om_1",
                    "message_type": "text",
                    "content": '{"text":"会议号：987-654-321"}',
                },
            },
        }
    )

    assert message["event_id"] == "evt_1"
    assert message["conversation_key"] == "oc_1"
    assert message["message_id"] == "om_1"
    assert message["sender_key"] == "ou_1"
    assert message["text"] == "会议号：987-654-321"


def test_meeting_proposal_uses_tmeet_completion_when_enabled(monkeypatch) -> None:
    from personal_affairs.api.routes import integrations_feishu
    from personal_affairs.application.tmeet_adapter import TMeetLookupResult

    def fake_lookup(cfg, *, meeting_id=None):
        assert meeting_id == "987654321"
        return TMeetLookupResult(
            status="success",
            details={
                "subject": "产品例会",
                "start_time": "2026-08-26T14:30:00+08:00",
                "end_time": "2026-08-26T15:00:00+08:00",
                "join_url": "https://meeting.tencent.com/dm/AbCdEf1234",
            },
            elapsed_ms=3,
        )

    monkeypatch.setattr(integrations_feishu, "lookup_tencent_meeting", fake_lookup)
    proposal = integrations_feishu._proposal_from_text(
        "会议号：987-654-321",
        "om_1",
        Settings(tmeet_enabled=True),
    )

    assert proposal.proposed_payload["title"] == "产品例会"
    assert proposal.proposed_payload["start_at"] == "2026-08-26T14:30:00+08:00"
    assert proposal.evidence["tmeet_lookup"] == {"status": "success", "elapsed_ms": 3}
    assert proposal.evidence["raw_snippet"] == "会议号：987-654-321"


def _encrypt_feishu_payload(payload: dict, encrypt_key: str) -> str:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    padding = 16 - (len(body) % 16)
    padded = body + bytes([padding]) * padding
    key = sha256(encrypt_key.encode("utf-8")).digest()
    iv = b"0123456789abcdef"
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return b64encode(iv + ciphertext).decode("ascii")
