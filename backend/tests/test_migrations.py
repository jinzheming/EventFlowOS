from pathlib import Path

from personal_affairs.storage import migrations


def test_run_migrations_records_each_sql_file(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "001_initial.sql").write_text("CREATE SCHEMA personal_affairs;", encoding="utf-8")
    (tmp_path / "002_feature.sql").write_text("ALTER TABLE personal_affairs.items ADD COLUMN x text;", encoding="utf-8")
    executed: list[tuple[str, tuple[str, ...] | None]] = []
    committed = False

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        def execute(self, sql: str, params: tuple[str, ...] | None = None) -> None:
            executed.append((sql, params))

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def commit(self) -> None:
            nonlocal committed
            committed = True

    monkeypatch.setattr(migrations, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(migrations.psycopg, "connect", lambda database_url: FakeConnection())

    assert migrations.run_migrations("postgresql://example") == ["001_initial.sql", "002_feature.sql"]
    assert committed is True
    recorded_versions = [params for sql, params in executed if "schema_migrations" in sql]
    assert recorded_versions == [("001_initial",), ("002_feature",)]
