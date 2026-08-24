import json
from hashlib import sha256
from hmac import compare_digest
from typing import Any, cast

from fastapi import APIRouter, Depends, Header, Request
from psycopg import Connection

from personal_affairs.api.dependencies import settings
from personal_affairs.api.schemas import AgentProposalCreate
from personal_affairs.application.agent_proposal_service import AgentProposalService
from personal_affairs.application.meeting_invite_parser import (
    MeetingInviteParseResult,
    merge_tmeet_meeting_details,
    parse_tencent_meeting_invite,
)
from personal_affairs.application.tmeet_adapter import lookup_tencent_meeting
from personal_affairs.config import Settings
from personal_affairs.domain.enums import AgentProposalRiskTier, AgentProposalSourceType
from personal_affairs.domain.errors import DomainError, ErrorCode
from personal_affairs.storage.database import get_pool
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.agent_ingest_events import AgentIngestEventsRepository
from personal_affairs.storage.repositories.agent_proposals import AgentProposalsRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.users import UsersRepository

router = APIRouter(prefix="/integrations/feishu/im", tags=["integrations"])


@router.post("/events")
async def feishu_im_events(
    request: Request,
    x_lark_request_timestamp: str | None = Header(default=None),
    x_lark_request_nonce: str | None = Header(default=None),
    x_lark_signature: str | None = Header(default=None),
    cfg: Settings = Depends(settings),
) -> dict[str, Any]:
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise DomainError(ErrorCode.INVALID_REQUEST, "Feishu request body must be valid JSON.", 400) from exc
    if not isinstance(payload, dict):
        raise DomainError(ErrorCode.INVALID_REQUEST, "Feishu request body must be a JSON object.", 400)
    if _is_challenge(payload):
        _verify_token(payload, cfg)
        return {"challenge": payload["challenge"]}
    if not cfg.feishu_im_enabled:
        raise DomainError(ErrorCode.NOT_FOUND, "Feishu IM integration is disabled.", 404)
    _verify_signature(body, cfg, x_lark_request_timestamp, x_lark_request_nonce, x_lark_signature)
    _verify_token(payload, cfg)

    message = extract_feishu_text_message(payload)
    if message["message_type"] != "text" or not message["text"]:
        return {"ok": True, "ignored": "unsupported_message_type"}
    text = cast(str, message["text"])

    with get_pool(cfg).connection() as conn:
        try:
            user = _resolve_default_user(conn, cfg)
            digest = sha256(body).hexdigest()
            ingest = AgentIngestEventsRepository(conn).record_received(
                user["id"],
                {
                    "source_type": "feishu_im",
                    "tenant_key": message["tenant_key"],
                    "conversation_key": message["conversation_key"],
                    "event_id": message["event_id"],
                    "message_id": message["message_id"],
                    "sender_key": message["sender_key"],
                    "payload_digest": digest,
                    "text_preview": text[:500],
                },
            )
            if ingest["status"] != "received":
                conn.commit()
                return {
                    "ok": True,
                    "duplicate": True,
                    "status": ingest["status"],
                    "proposal_id": ingest.get("proposal_id"),
                }

            proposal = _proposal_from_text(text, message["message_id"], cfg)
            created = AgentProposalService(
                AgentProposalsRepository(conn),
                ItemsRepository(conn),
                ActivityRepository(conn),
            ).propose(user["id"], proposal)
            AgentIngestEventsRepository(conn).mark_status(
                user["id"], ingest["id"], "proposal_created", proposal_id=created["id"]
            )
            conn.commit()
            return {"ok": True, "proposal_id": str(created["id"]), "duplicate": False}
        except Exception:
            conn.rollback()
            raise


def _is_challenge(payload: dict[str, Any]) -> bool:
    return payload.get("type") == "url_verification" and bool(payload.get("challenge"))


def _verify_token(payload: dict[str, Any], cfg: Settings) -> None:
    expected = cfg.feishu_im_verification_token
    header = payload.get("header") or {}
    header_token = header.get("token") if isinstance(header, dict) else None
    token = payload.get("token") or header_token
    if expected and token != expected:
        raise DomainError(ErrorCode.AUTH_REQUIRED, "Feishu verification token mismatch.", 401)


def _verify_signature(
    body: bytes,
    cfg: Settings,
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
) -> None:
    if not cfg.feishu_im_encrypt_key:
        return
    if not timestamp or not nonce or not signature:
        raise DomainError(ErrorCode.AUTH_REQUIRED, "Feishu signature headers are required.", 401)
    base = f"{timestamp}{nonce}{cfg.feishu_im_encrypt_key}".encode() + body
    expected = sha256(base).hexdigest()
    if not compare_digest(expected, signature):
        raise DomainError(ErrorCode.AUTH_REQUIRED, "Feishu request signature mismatch.", 401)


def extract_feishu_text_message(payload: dict[str, Any]) -> dict[str, str | None]:
    header = _dict_or_empty(payload.get("header"))
    event = _dict_or_empty(payload.get("event"))
    message = _dict_or_empty(event.get("message") or event)
    content = _message_content(message.get("content"))
    sender = _dict_or_empty(event.get("sender"))
    sender_id = _dict_or_empty(sender.get("sender_id"))
    return {
        "event_id": header.get("event_id") or payload.get("uuid"),
        "tenant_key": header.get("tenant_key") or payload.get("tenant_key") or "default",
        "conversation_key": message.get("chat_id") or event.get("chat_id") or "default",
        "message_id": message.get("message_id") or event.get("message_id"),
        "message_type": message.get("message_type") or event.get("message_type") or "unknown",
        "sender_key": sender_id.get("open_id") or sender_id.get("user_id") or sender.get("open_id"),
        "text": content.get("text") or content.get("content"),
    }


def _message_content(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {"text": raw}
        return decoded if isinstance(decoded, dict) else {"text": raw}
    return {}


def _dict_or_empty(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _resolve_default_user(conn: Connection, cfg: Settings) -> dict:
    users = UsersRepository(conn)
    if cfg.feishu_im_default_user_id:
        user = users.get_by_id(cfg.feishu_im_default_user_id)
        if user:
            return user
    if cfg.feishu_im_default_username:
        user = users.get_by_username(cfg.feishu_im_default_username)
        if user:
            return user
    if cfg.bootstrap_username:
        user = users.get_by_username(cfg.bootstrap_username)
        if user:
            return user
    raise DomainError(ErrorCode.AUTH_REQUIRED, "Feishu IM default user is not configured.", 401)


def _proposal_from_text(text: str, message_id: str | None, cfg: Settings) -> AgentProposalCreate:
    parsed = parse_tencent_meeting_invite(text, cfg.default_timezone)
    tmeet_lookup: dict[str, Any] | None = None
    if _should_lookup_tmeet(parsed, cfg):
        lookup = lookup_tencent_meeting(cfg, meeting_id=parsed.meeting_id)
        tmeet_lookup = lookup.audit
        if lookup.status == "success" and lookup.details:
            parsed = merge_tmeet_meeting_details(parsed, lookup.details, cfg.default_timezone)
    is_meeting_like = "腾讯会议" in text or parsed.meeting_id or parsed.join_url
    if is_meeting_like:
        evidence = {
            "parser": "tencent_meeting_invite",
            "raw_snippet": _snippet(text),
            "confidence": parsed.confidence,
            "meeting_id": parsed.meeting_id,
            "meeting_code": parsed.meeting_code,
            "join_url": parsed.join_url,
            "missing_fields": parsed.missing_fields,
        }
        if tmeet_lookup:
            evidence["tmeet_lookup"] = tmeet_lookup
        return AgentProposalCreate(
            source_type=AgentProposalSourceType.FEISHU_IM,
            source_ref=message_id,
            risk_tier=AgentProposalRiskTier.L2,
            confidence=parsed.confidence,
            proposed_payload=parsed.proposed_item,
            evidence=evidence,
            reason="Parsed from Feishu IM Tencent Meeting text.",
        )
    return AgentProposalCreate(
        source_type=AgentProposalSourceType.FEISHU_IM,
        source_ref=message_id,
        risk_tier=AgentProposalRiskTier.L2,
        confidence=0.4,
        proposed_payload={"title": _generic_title(text), "scope": "work", "status": "inbox", "notes": text},
        evidence={"raw_snippet": _snippet(text)},
        reason="Forwarded Feishu IM text requires confirmation.",
    )


def _should_lookup_tmeet(parsed: MeetingInviteParseResult, cfg: Settings) -> bool:
    return cfg.tmeet_enabled and bool(parsed.meeting_id) and bool({"title", "schedule"} & set(parsed.missing_fields))


def _generic_title(text: str) -> str:
    first = text.strip().splitlines()[0].strip() if text.strip() else "飞书转入事项"
    return first[:120] or "飞书转入事项"


def _snippet(text: str, limit: int = 2000) -> str:
    return text.strip()[:limit]
