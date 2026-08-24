from typing import Any
from uuid import UUID

from personal_affairs.api.schemas import (
    AgentProposalApprove,
    AgentProposalCreate,
    ItemCreate,
    ItemPatch,
    ReminderPut,
)
from personal_affairs.application.item_service import ItemService
from personal_affairs.application.reminder_service import ReminderService
from personal_affairs.config import Settings
from personal_affairs.domain.enums import AgentProposalAction, AgentProposalState, ReminderTiming
from personal_affairs.domain.errors import DomainError, ErrorCode, conflict_error
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.agent_proposals import AgentProposalsRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository


class AgentProposalService:
    def __init__(
        self,
        proposals: AgentProposalsRepository,
        items: ItemsRepository,
        activity: ActivityRepository,
        reminders: RemindersRepository | None = None,
        settings: Settings | None = None,
    ):
        self.proposals = proposals
        self.items = items
        self.activity = activity
        self.reminders = reminders
        self.settings = settings

    def propose(self, user_id: UUID, request: AgentProposalCreate) -> dict:
        proposal = self.proposals.create(user_id, request.model_dump(mode="json", exclude_none=True))
        self.activity.record(
            user_id,
            "agent_proposal",
            proposal["id"],
            "created",
            {"source_type": proposal["source_type"], "risk_tier": proposal["risk_tier"]},
        )
        return proposal

    def approve(self, user_id: UUID, proposal_id: UUID, request: AgentProposalApprove) -> tuple[dict, dict | None]:
        proposal = self.proposals.get_for_update(user_id, proposal_id)
        if proposal is None:
            return {}, None
        if proposal["state"] in {AgentProposalState.APPROVED.value, AgentProposalState.EDITED_APPROVED.value}:
            item = self.items.get_item(user_id, proposal["applied_item_id"]) if proposal.get("applied_item_id") else None
            return proposal, item
        if proposal["state"] != AgentProposalState.PENDING.value:
            raise conflict_error(ErrorCode.PROPOSAL_ALREADY_DECIDED, "Proposal was already decided.")

        payload = dict(request.edited_payload if request.edited_payload is not None else proposal["proposed_payload"])
        source_context = {
            "proposal_id": str(proposal["id"]),
            "source_type": proposal["source_type"],
            "source_ref": proposal.get("source_ref"),
        }
        source_context.update(_source_context_from_evidence(proposal.get("evidence") or {}))
        item = self._apply_payload(user_id, proposal, payload, source_context)
        next_state = (
            AgentProposalState.EDITED_APPROVED.value
            if request.edited_payload is not None
            else AgentProposalState.APPROVED.value
        )
        updated = self.proposals.mark_decided(
            user_id,
            proposal_id,
            next_state,
            "human",
            request.decision_note,
            item["id"] if item else None,
            payload if request.edited_payload is not None else None,
        )
        assert updated is not None
        self.activity.record(
            user_id,
            "agent_proposal",
            proposal_id,
            next_state,
            {"applied_item_id": str(item["id"]) if item else None},
        )
        return updated, item

    def reject(self, user_id: UUID, proposal_id: UUID, state: AgentProposalState, decision_note: str | None) -> dict | None:
        proposal = self.proposals.get_for_update(user_id, proposal_id)
        if proposal is None:
            return None
        if proposal["state"] != AgentProposalState.PENDING.value:
            raise conflict_error(ErrorCode.PROPOSAL_ALREADY_DECIDED, "Proposal was already decided.")
        updated = self.proposals.mark_decided(user_id, proposal_id, state.value, "human", decision_note)
        if updated:
            self.activity.record(user_id, "agent_proposal", proposal_id, state.value, {})
        return updated

    def _apply_payload(
        self,
        user_id: UUID,
        proposal: dict[str, Any],
        payload: dict[str, Any],
        source_context: dict[str, Any],
    ) -> dict | None:
        action = proposal["proposed_action"]
        service = ItemService(self.items, self.activity)
        if action == AgentProposalAction.CREATE_ITEM.value:
            payload["client_request_id"] = f"proposal:{proposal['id']}"
            item, _ = service.create(
                user_id,
                ItemCreate(**payload),
                created_by_actor="agent",
                source_context=source_context,
            )
            self._maybe_create_default_meeting_reminder(user_id, item, source_context)
            return item
        if action == AgentProposalAction.PATCH_ITEM.value:
            target_item_id = proposal.get("target_item_id") or payload.pop("target_item_id", None)
            if not target_item_id:
                raise DomainError(ErrorCode.NOT_FOUND, "Proposal target item is missing.", 404)
            current = self.items.get_item(user_id, target_item_id)
            if not current:
                raise DomainError(ErrorCode.NOT_FOUND, "Proposal target item was not found.", 404)
            expected_version = int(payload.pop("expected_version", current["version"]))
            return service.patch(
                user_id,
                target_item_id,
                current,
                expected_version,
                ItemPatch(**payload),
                updated_by_actor="agent",
                source_context=source_context,
            )
        raise conflict_error(ErrorCode.PROPOSAL_ACTION_UNSUPPORTED, "Proposal action is not supported.")

    def _maybe_create_default_meeting_reminder(
        self,
        user_id: UUID,
        item: dict[str, Any],
        source_context: dict[str, Any],
    ) -> None:
        if self.reminders is None or self.settings is None:
            return
        if not source_context.get("meeting_meta"):
            return
        if not item.get("start_at"):
            return
        ReminderService(self.reminders, self.items, self.settings).upsert(
            user_id,
            item["id"],
            ReminderPut(
                timing=ReminderTiming.BEFORE_START,
                offset_minutes=10,
                timezone=self.settings.default_timezone,
                external_enabled=True,
            ),
        )


def _source_context_from_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    source_context: dict[str, Any] = {}
    if evidence.get("parser"):
        source_context["parser"] = evidence["parser"]
    if evidence.get("confidence") is not None:
        source_context["confidence"] = evidence["confidence"]
    if evidence.get("join_url"):
        source_context["external_url"] = evidence["join_url"]
    meeting_meta = {
        key: evidence[key]
        for key in ("meeting_id", "meeting_code", "join_url")
        if evidence.get(key)
    }
    if meeting_meta:
        source_context["meeting_meta"] = meeting_meta
    if evidence.get("tmeet_lookup"):
        source_context["tmeet_lookup"] = evidence["tmeet_lookup"]
    return source_context
