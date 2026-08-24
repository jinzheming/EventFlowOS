from typing import Any, cast
from uuid import UUID, uuid4

from personal_affairs.api.schemas import (
    AgentProposalApprove,
    AgentProposalCreate,
    AgentProposalReject,
)
from personal_affairs.application import agent_proposal_service as service_module
from personal_affairs.application.agent_proposal_service import AgentProposalService
from personal_affairs.domain.enums import AgentProposalState


class FakeProposals:
    def __init__(self, proposal: dict[str, Any] | None = None):
        self.proposal = proposal
        self.decisions: list[dict[str, Any]] = []

    def create(self, user_id: UUID, payload: dict[str, Any]) -> dict:
        self.proposal = {
            "id": uuid4(),
            "source_type": payload["source_type"],
            "source_ref": payload.get("source_ref"),
            "risk_tier": payload["risk_tier"],
            "confidence": payload.get("confidence"),
            "state": "pending",
            "proposed_action": payload["proposed_action"],
            "proposed_payload": payload["proposed_payload"],
            "evidence": payload.get("evidence") or {},
            "reason": payload.get("reason"),
            "target_item_id": payload.get("target_item_id"),
            "applied_item_id": None,
            "expires_at": payload.get("expires_at"),
            "decided_at": None,
            "decided_by_actor": None,
            "decision_note": None,
            "created_at": None,
            "updated_at": None,
        }
        return self.proposal

    def get_for_update(self, user_id: UUID, proposal_id: UUID) -> dict | None:
        if self.proposal and self.proposal["id"] == proposal_id:
            return self.proposal
        return None

    def mark_decided(self, user_id: UUID, proposal_id: UUID, state: str, decided_by_actor: str, decision_note=None, applied_item_id=None, proposed_payload=None) -> dict | None:
        assert self.proposal is not None
        self.proposal = self.proposal | {
            "state": state,
            "decided_by_actor": decided_by_actor,
            "decision_note": decision_note,
            "applied_item_id": applied_item_id,
            "proposed_payload": proposed_payload or self.proposal["proposed_payload"],
        }
        self.decisions.append(self.proposal)
        return self.proposal


class FakeItems:
    def __init__(self):
        self.item = {"id": uuid4(), "version": 1, "status": "planned"}

    def get_item(self, user_id: UUID, item_id: UUID) -> dict | None:
        return self.item if item_id == self.item["id"] else None


class FakeActivity:
    def __init__(self):
        self.events: list[tuple[str, UUID, str, dict[str, Any]]] = []

    def record(self, user_id: UUID, entity_type: str, entity_id: UUID, action: str, payload: dict[str, Any]) -> None:
        self.events.append((entity_type, entity_id, action, payload))


class FakeItemService:
    calls: list[dict[str, Any]] = []

    def __init__(self, items: FakeItems, activity: FakeActivity):
        self.items = items

    def create(self, user_id: UUID, request, **kwargs) -> tuple[dict, bool]:
        self.calls.append({"request": request, "kwargs": kwargs})
        return self.items.item, True


class FakeReminderService:
    calls: list[dict[str, Any]] = []

    def __init__(self, reminders, items, settings):
        self.reminders = reminders
        self.items = items
        self.settings = settings

    def upsert(self, user_id: UUID, item_id: UUID, request) -> dict:
        self.calls.append({"user_id": user_id, "item_id": item_id, "request": request})
        return {"item_id": item_id, "timing": request.timing.value, "offset_minutes": request.offset_minutes}


class FakeSettings:
    default_timezone = "Asia/Shanghai"


def test_propose_records_pending_candidate() -> None:
    user_id = uuid4()
    proposals = FakeProposals()
    service = AgentProposalService(proposals, FakeItems(), FakeActivity())

    proposal = service.propose(
        user_id,
        AgentProposalCreate(
            proposed_payload={"title": "整理会议", "scope": "work"},
            reason="forwarded text",
        ),
    )

    assert proposal["state"] == "pending"
    assert proposal["proposed_payload"]["title"] == "整理会议"


def test_approve_create_item_uses_proposal_idempotency(monkeypatch) -> None:
    user_id = uuid4()
    proposal_id = uuid4()
    proposals = FakeProposals({
        "id": proposal_id,
        "source_type": "agent",
        "source_ref": "unit",
        "state": "pending",
        "proposed_action": "create_item",
        "proposed_payload": {"title": "确认会议", "scope": "work"},
    })
    items = FakeItems()
    activity = FakeActivity()
    FakeItemService.calls = []
    monkeypatch.setattr(service_module, "ItemService", FakeItemService)

    proposal, item = AgentProposalService(proposals, items, activity).approve(user_id, proposal_id, AgentProposalApprove())

    assert item == items.item
    assert proposal["state"] == "approved"
    assert FakeItemService.calls[0]["request"].client_request_id == f"proposal:{proposal_id}"
    assert FakeItemService.calls[0]["kwargs"]["created_by_actor"] == "agent"
    assert FakeItemService.calls[0]["kwargs"]["source_context"]["proposal_id"] == str(proposal_id)

    proposal, item = AgentProposalService(proposals, items, activity).approve(user_id, proposal_id, AgentProposalApprove())
    assert proposal["state"] == "approved"
    assert item == items.item
    assert len(FakeItemService.calls) == 1


def test_approve_tencent_meeting_creates_default_reminder_once(monkeypatch) -> None:
    user_id = uuid4()
    proposal_id = uuid4()
    proposals = FakeProposals({
        "id": proposal_id,
        "source_type": "feishu_im",
        "source_ref": "msg-1",
        "state": "pending",
        "proposed_action": "create_item",
        "proposed_payload": {
            "title": "项目例会",
            "scope": "work",
            "status": "planned",
            "all_day": False,
            "start_at": "2026-08-24T10:00:00+08:00",
        },
        "evidence": {
            "parser": "tencent_meeting_invite_v1",
            "confidence": 0.9,
            "meeting_id": "987654321",
            "join_url": "https://meeting.tencent.com/dm/example",
        },
    })
    items = FakeItems()
    items.item = items.item | {"start_at": "2026-08-24T10:00:00+08:00"}
    FakeItemService.calls = []
    FakeReminderService.calls = []
    monkeypatch.setattr(service_module, "ItemService", FakeItemService)
    monkeypatch.setattr(service_module, "ReminderService", FakeReminderService)

    service = AgentProposalService(
        proposals,
        items,
        FakeActivity(),
        reminders=cast(Any, object()),
        settings=cast(Any, FakeSettings()),
    )
    proposal, item = service.approve(user_id, proposal_id, AgentProposalApprove())

    assert proposal["state"] == "approved"
    assert item == items.item
    assert len(FakeReminderService.calls) == 1
    reminder = FakeReminderService.calls[0]["request"]
    assert reminder.timing.value == "before_start"
    assert reminder.offset_minutes == 10
    assert reminder.timezone == "Asia/Shanghai"
    assert reminder.external_enabled is True

    service.approve(user_id, proposal_id, AgentProposalApprove())
    assert len(FakeReminderService.calls) == 1


def test_reject_does_not_apply_item() -> None:
    user_id = uuid4()
    proposal_id = uuid4()
    proposals = FakeProposals({
        "id": proposal_id,
        "state": "pending",
        "source_type": "agent",
        "proposed_action": "create_item",
        "proposed_payload": {"title": "忽略", "scope": "work"},
    })

    proposal = AgentProposalService(proposals, FakeItems(), FakeActivity()).reject(
        user_id,
        proposal_id,
        AgentProposalState.REJECTED,
        AgentProposalReject(decision_note="not needed").decision_note,
    )

    assert proposal is not None
    assert proposal["state"] == "rejected"
    assert proposal["applied_item_id"] is None
