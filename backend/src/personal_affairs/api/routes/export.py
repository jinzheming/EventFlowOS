import json
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from psycopg import Connection

from personal_affairs.api.dependencies import current_user_id, db_conn

router = APIRouter(tags=["export"])

_EXPORT_TABLES = [
    ("items", "SELECT * FROM personal_affairs.items WHERE user_id = %s ORDER BY created_at"),
    ("projects", "SELECT * FROM personal_affairs.projects WHERE user_id = %s ORDER BY created_at"),
    ("milestones", "SELECT * FROM personal_affairs.milestones WHERE user_id = %s ORDER BY created_at"),
    ("tags", "SELECT * FROM personal_affairs.tags WHERE user_id = %s ORDER BY created_at"),
    ("people", "SELECT * FROM personal_affairs.people WHERE user_id = %s ORDER BY created_at"),
    (
        "item_tags",
        "SELECT it.* FROM personal_affairs.item_tags it "
        "JOIN personal_affairs.items i ON i.id = it.item_id WHERE i.user_id = %s",
    ),
    (
        "item_people",
        "SELECT ip.* FROM personal_affairs.item_people ip "
        "JOIN personal_affairs.items i ON i.id = ip.item_id WHERE i.user_id = %s",
    ),
    ("reminders", "SELECT * FROM personal_affairs.reminders WHERE user_id = %s ORDER BY created_at"),
    ("preferences", "SELECT * FROM personal_affairs.user_preferences WHERE user_id = %s"),
]


def _json_safe(value: object) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"not exportable: {type(value)}")


@router.get("/export")
def export_data(
    user_id: UUID = Depends(current_user_id),
    conn: Connection = Depends(db_conn),
) -> Response:
    payload: dict = {"exported_at": datetime.now(UTC).isoformat(), "format_version": 1}
    for name, sql in _EXPORT_TABLES:
        payload[name] = [dict(row) for row in conn.execute(sql, (user_id,)).fetchall()]
    filename = f"personal-affairs-export-{datetime.now(UTC).date().isoformat()}.json"
    return Response(
        content=json.dumps(payload, ensure_ascii=False, default=_json_safe),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
