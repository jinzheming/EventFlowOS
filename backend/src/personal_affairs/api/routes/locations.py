from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn, settings
from personal_affairs.api.schemas import LocationResolveRequest
from personal_affairs.application.integration_settings import settings_for_user
from personal_affairs.application.location_service import AMapClient
from personal_affairs.config import Settings

router = APIRouter(prefix="/locations", tags=["locations"])


@router.post("/resolve")
def resolve_location(
    request: LocationResolveRequest,
    cfg: Settings = Depends(settings),
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> dict:
    """Resolve an address/POI server-side; the AMap key never reaches the browser."""
    client = AMapClient(settings_for_user(conn, user_id, cfg))
    if request.search_poi:
        poi = client.search_poi(request.query, city=request.city, limit=request.limit)
        if poi.get("candidates"):
            return poi
    return client.resolve(request.query, city=request.city, adcode=request.adcode, limit=request.limit)
