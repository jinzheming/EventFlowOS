from typing import Any
from uuid import UUID

from personal_affairs.storage.repositories.people import PeopleRepository


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class PeopleService:
    def __init__(self, people: PeopleRepository):
        self.people = people

    def create(self, user_id: UUID, name: str, identity: str | None, note: str | None) -> dict:
        return self.people.create(user_id, name.strip(), _clean_text(identity), _clean_text(note))

    def patch(self, user_id: UUID, person_id: UUID, patch: dict[str, Any]) -> dict | None:
        if "name" in patch and patch["name"] is not None:
            patch["name"] = patch["name"].strip()
        if "identity" in patch:
            patch["identity"] = _clean_text(patch["identity"])
        if "note" in patch:
            patch["note"] = _clean_text(patch["note"])
        return self.people.patch(user_id, person_id, patch)
