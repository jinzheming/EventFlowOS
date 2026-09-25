from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, settings
from personal_affairs.api.schemas import ScheduleFeasibilityRequest
from personal_affairs.application.integration_settings import settings_for_user
from personal_affairs.application.location_service import AMapClient
from personal_affairs.application.schedule_feasibility import assess_schedule_feasibility
from personal_affairs.config import Settings
from personal_affairs.storage.repositories.items import ItemsRepository

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/assess-feasibility")
def assess_feasibility(
    request: ScheduleFeasibilityRequest,
    cfg: Settings = Depends(settings),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    return assess_schedule_feasibility(
        ItemsRepository(conn), user_id, request.item_ids, AMapClient(settings_for_user(conn, user_id, cfg)),
        travel_mode=request.travel_mode, buffer_minutes=request.buffer_minutes,
    )
