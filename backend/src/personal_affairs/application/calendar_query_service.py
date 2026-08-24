from datetime import date, datetime
from uuid import UUID

from personal_affairs.storage.repositories.items import ItemsRepository
from personal_affairs.storage.repositories.projects import ProjectsRepository


class CalendarQueryService:
    def __init__(self, items: ItemsRepository, projects: ProjectsRepository):
        self.items = items
        self.projects = projects

    def events(self, user_id: UUID, start: str, end: str, kinds: set[str] | None = None) -> list[dict]:
        selected = kinds or {"work_item", "personal_item", "milestone"}
        events: list[dict] = []
        if "work_item" in selected or "personal_item" in selected:
            for item in self.items.list_calendar_items(user_id, starts_before=end, ends_after=start):
                kind = "work_item" if item["scope"] == "work" else "personal_item"
                if kind not in selected:
                    continue
                event_start: date | datetime | None
                event_end: date | datetime | None
                if item["all_day"]:
                    event_start = item["start_date"] or item["due_date"]
                    event_end = item["due_date"] if item["start_date"] else None
                else:
                    event_start = item["start_at"] or item["due_at"]
                    event_end = item["due_at"] if item["start_at"] else None
                if event_start is None:
                    continue
                events.append(
                    {
                        "id": f"{kind}:{item['id']}",
                        "kind": kind,
                        "title": item["title"],
                        "start": event_start,
                        "end": event_end,
                        "all_day": item["all_day"],
                        "source_id": item["id"],
                        "project_id": item["project_id"],
                        "status": item["status"],
                        "color": "#0F766E" if kind == "work_item" else "#CA8A04",
                    }
                )
        if "milestone" in selected:
            for milestone in self.projects.list_calendar_milestones(user_id, end, start):
                events.append(
                    {
                        "id": f"milestone:{milestone['id']}",
                        "kind": "milestone",
                        "title": milestone["title"],
                        "start": milestone["due_date"],
                        "end": None,
                        "all_day": True,
                        "source_id": milestone["id"],
                        "project_id": milestone["project_id"],
                        "status": milestone["status"],
                        "color": milestone["color"] or "#334155",
                    }
                )
        return events
