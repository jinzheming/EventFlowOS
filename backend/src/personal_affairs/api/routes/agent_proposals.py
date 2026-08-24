from uuid import UUID

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, require_csrf
from personal_affairs.api.problem_details import not_found
from personal_affairs.api.schemas import (
    AgentProposalApprove,
    AgentProposalCreate,
    AgentProposalDecisionOut,
    AgentProposalOut,
    AgentProposalReject,
)
from personal_affairs.application.agent_proposal_service import AgentProposalService
from personal_affairs.config import get_settings
from personal_affairs.domain.enums import AgentProposalState
from personal_affairs.storage.repositories.activity import ActivityRepository
from personal_affairs.storage.repositories.agent_proposals import AgentProposalsRepository
from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.reminders import RemindersRepository

router = APIRouter(prefix="/agent-proposals", tags=["agent-proposals"])


def _service(conn: Connection) -> AgentProposalService:
    return AgentProposalService(
        AgentProposalsRepository(conn),
        ItemsRepository(conn),
        ActivityRepository(conn),
        RemindersRepository(conn),
        get_settings(),
    )


@router.get("", response_model=list[AgentProposalOut])
def list_agent_proposals(
    state: AgentProposalState | None = AgentProposalState.PENDING,
    limit: int = Query(100, ge=1, le=500),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> list[dict]:
    return AgentProposalsRepository(conn).list_pending(user_id, state.value if state else None, limit)


@router.post("", response_model=AgentProposalOut, dependencies=[Depends(require_csrf)])
def create_agent_proposal(
    request: AgentProposalCreate,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return _service(conn).propose(user_id, request)


@router.get("/{proposal_id}", response_model=AgentProposalOut)
def get_agent_proposal(
    proposal_id: UUID,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    proposal = AgentProposalsRepository(conn).get(user_id, proposal_id)
    if not proposal:
        return not_found()
    return proposal


@router.post("/{proposal_id}/approve", response_model=AgentProposalDecisionOut, dependencies=[Depends(require_csrf)])
def approve_agent_proposal(
    proposal_id: UUID,
    request: AgentProposalApprove,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    proposal, item = _service(conn).approve(user_id, proposal_id, request)
    if not proposal:
        return not_found()
    return {"proposal": proposal, "item": item}


@router.post("/{proposal_id}/reject", response_model=AgentProposalOut, dependencies=[Depends(require_csrf)])
def reject_agent_proposal(
    proposal_id: UUID,
    request: AgentProposalReject,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    proposal = _service(conn).reject(user_id, proposal_id, AgentProposalState.REJECTED, request.decision_note)
    if not proposal:
        return not_found()
    return proposal


@router.post("/{proposal_id}/ignore", response_model=AgentProposalOut, dependencies=[Depends(require_csrf)])
def ignore_agent_proposal(
    proposal_id: UUID,
    request: AgentProposalReject,
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    proposal = _service(conn).reject(user_id, proposal_id, AgentProposalState.IGNORED, request.decision_note)
    if not proposal:
        return not_found()
    return proposal
