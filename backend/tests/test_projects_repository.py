from uuid import uuid4

from personal_affairs.storage.repositories.projects import ProjectsRepository


class RecordingConnection:
    def __init__(self) -> None:
        self.query = ""
        self.params = ()

    def execute(self, query: str, params: tuple[object, ...]):
        self.query = query
        self.params = params
        return self

    def fetchall(self) -> list[dict]:
        return []


def test_list_projects_qualifies_archived_at_when_joining_groups() -> None:
    conn = RecordingConnection()
    ProjectsRepository(conn).list_projects(uuid4())

    assert "AND p.archived_at IS NULL" in conn.query
    assert "AND archived_at IS NULL" not in conn.query
