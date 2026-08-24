from typing import Any
from uuid import UUID

from personal_affairs.domain.policies import validate_tag_parent
from personal_affairs.storage.repositories.tags import TagsRepository


class TagService:
    def __init__(self, tags: TagsRepository):
        self.tags = tags

    def create(self, user_id: UUID, name: str, color: str, parent_id: UUID | None) -> dict:
        if parent_id is not None:
            parent = self.tags.get(user_id, parent_id)
            validate_tag_parent(None, parent_id, parent, None, False)
        return self.tags.create(user_id, name.strip(), color, parent_id)

    def patch(self, user_id: UUID, tag_id: UUID, patch: dict[str, Any]) -> dict | None:
        current = self.tags.get(user_id, tag_id)
        if not current:
            return None
        if "parent_id" in patch:
            new_parent = patch["parent_id"]
            parent = self.tags.get(user_id, new_parent) if new_parent is not None else None
            validate_tag_parent(
                tag_id,
                new_parent,
                parent,
                current,
                self.tags.has_children(user_id, tag_id),
            )
        if "name" in patch and patch["name"] is not None:
            patch["name"] = patch["name"].strip()
        return self.tags.patch(user_id, tag_id, patch)
