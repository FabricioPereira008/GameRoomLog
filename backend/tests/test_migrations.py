import sqlalchemy as sa
from sqlalchemy import inspect

from backend.app.core.database import Base
from backend.app.core.migrations import BASELINE_REVISION, run_migrations

HEAD_REVISION = "0004_genre_position"
import backend.app.models  # noqa: F401


def _engine(tmp_path):
    return sa.create_engine(f"sqlite:///{tmp_path / 'test.db'}")


def test_new_database_gets_full_schema_and_version(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"games", "genres", "platforms", "franchises", "developers", "game_genres", "alembic_version", "game_store_links", "ignored_store_games", "inbox_events"} <= tables
    with engine.connect() as c:
        assert c.execute(sa.text("select version_num from alembic_version")).scalar() == HEAD_REVISION


def test_migrations_are_idempotent(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    run_migrations(engine)


def test_legacy_database_is_adopted_without_losing_data(tmp_path):
    engine = _engine(tmp_path)
    # como versões antigas criavam o banco (sem as tabelas posteriores à baseline)
    later = {"game_store_links", "ignored_store_games", "inbox_events"}
    Base.metadata.create_all(engine, tables=[t for n, t in Base.metadata.tables.items() if n not in later])
    with engine.begin() as c:
        c.execute(sa.text("alter table game_genres drop column position"))  # coluna da 0004
        c.execute(sa.text("insert into genres (name, color) values ('RPG', '#fff')"))
    run_migrations(engine)
    with engine.connect() as c:
        assert c.execute(sa.text("select name from genres")).scalar() == "RPG"
        assert c.execute(sa.text("select version_num from alembic_version")).scalar() == HEAD_REVISION
    assert "position" in {col["name"] for col in inspect(engine).get_columns("game_genres")}


def test_models_and_migrations_have_no_drift(tmp_path):
    """Falha se um model mudar sem a migração correspondente."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    engine = _engine(tmp_path)
    run_migrations(engine)
    with engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata)
    assert diff == []


def test_app_lifespan_runs_migrations(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app import main
    engine = _engine(tmp_path)
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
    assert "games" in inspect(engine).get_table_names()
