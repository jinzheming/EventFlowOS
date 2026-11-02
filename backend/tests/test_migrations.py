from pathlib import Path

from personal_affairs.storage import migrations


class FakeDatabase:
    def __init__(self, applied: set[str] | None = None):
        self.applied = set(applied or ())
        self.tracking_exists = bool(self.applied)
        self.executed_sql: list[str] = []
        self.committed = False


class FakeCursor:
    def __init__(self, database: FakeDatabase):
        self.database = database
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query: str, params: tuple | None = None) -> None:
        if "SELECT to_regclass" in query:
            self.result = (self.database.tracking_exists,)
        elif "SELECT 1 FROM personal_affairs.schema_migrations" in query:
            assert params is not None
            self.result = (1,) if params[0] in self.database.applied else None
        elif "INSERT INTO personal_affairs.schema_migrations" in query:
            assert params is not None
            self.database.applied.add(params[0])
            self.database.tracking_exists = True
            self.result = None
        else:
            self.database.executed_sql.append(query)
            if "CREATE TABLE IF NOT EXISTS personal_affairs.schema_migrations" in query:
                self.database.tracking_exists = True
            self.result = None

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self, database: FakeDatabase):
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return FakeCursor(self.database)

    def commit(self):
        self.database.committed = True


def test_migrations_record_new_versions_and_skip_them(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "001_initial.sql").write_text(
        "CREATE TABLE IF NOT EXISTS personal_affairs.schema_migrations"
    )
    (tmp_path / "002_feature.sql").write_text("ALTER TABLE personal_affairs.items ADD feature")
    database = FakeDatabase()

    monkeypatch.setattr(migrations, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(
        migrations.psycopg,
        "connect",
        lambda database_url: FakeConnection(database),
    )

    assert migrations.run_migrations("postgresql://unused") == [
        "001_initial.sql",
        "002_feature.sql",
    ]
    assert migrations.run_migrations("postgresql://unused") == []
    assert len(database.executed_sql) == 2
    assert database.applied == {"001_initial", "002_feature"}
    assert database.committed


def test_migrations_fill_gaps_in_legacy_tracking(monkeypatch, tmp_path: Path) -> None:
    for name in ("001_initial", "002_old", "003_existing", "004_new"):
        (tmp_path / f"{name}.sql").write_text(f"-- {name}")
    database = FakeDatabase({"001_initial", "003_existing"})

    monkeypatch.setattr(migrations, "MIGRATIONS_DIR", tmp_path)
    monkeypatch.setattr(
        migrations.psycopg,
        "connect",
        lambda database_url: FakeConnection(database),
    )

    assert migrations.run_migrations("postgresql://unused") == [
        "002_old.sql",
        "004_new.sql",
    ]
    assert database.applied == {
        "001_initial",
        "002_old",
        "003_existing",
        "004_new",
    }
    assert database.executed_sql == ["-- 002_old", "-- 004_new"]
