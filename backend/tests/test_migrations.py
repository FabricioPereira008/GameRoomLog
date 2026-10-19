import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from backend.app.core.database import Base
from backend.app.core.migrations import BASELINE_REVISION, run_migrations

HEAD_REVISION = "0008_developer_from_relation"
import backend.app.models  # noqa: F401


def _engine(tmp_path):
    return sa.create_engine(f"sqlite:///{tmp_path / 'test.db'}")


def test_new_database_gets_full_schema_and_version(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"games", "genres", "platforms", "franchises", "developers", "game_genres", "alembic_version", "game_store_links", "ignored_store_games", "inbox_events", "yearbook_picks"} <= tables
    with engine.connect() as c:
        assert c.execute(sa.text("select version_num from alembic_version")).scalar() == HEAD_REVISION


def test_migrations_are_idempotent(tmp_path):
    engine = _engine(tmp_path)
    run_migrations(engine)
    run_migrations(engine)


def test_legacy_database_is_adopted_without_losing_data(tmp_path):
    engine = _engine(tmp_path)
    # como versões antigas criavam o banco (sem as tabelas posteriores à baseline)
    later = {"game_store_links", "ignored_store_games", "inbox_events", "yearbook_picks"}
    Base.metadata.create_all(engine, tables=[t for n, t in Base.metadata.tables.items() if n not in later])
    with engine.begin() as c:
        c.execute(sa.text("alter table game_genres drop column position"))  # coluna da 0004
        ops = Operations(MigrationContext.configure(c))
        ops.drop_index("ix_games_replay_of_id", table_name="games")  # coluna da 0007
        with ops.batch_alter_table("games") as batch:
            batch.drop_column("replay_of_id")
        c.execute(sa.text("alter table games add column developer varchar(150)"))  # removida na 0008
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
        replay_fk = [r for r in c.exec_driver_sql("pragma foreign_key_list(games)") if r[3] == "replay_of_id"]
    # A reflexão do SQLite não lê ON DELETE de FK declarada na coluna (ADD COLUMN ... REFERENCES,
    # da 0007): o autogenerate a vê como remove_fk + add_fk; a regra é conferida pelo PRAGMA.
    fk_cols = lambda op: [col.name for col in op[1].columns]
    diff = [op for op in diff if not (op[0] in ("remove_fk", "add_fk") and fk_cols(op) == ["replay_of_id"])]
    assert diff == []
    assert [(r[2], r[4], r[6]) for r in replay_fk] == [("games", "id", "SET NULL")]


def test_app_lifespan_runs_migrations(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app import main
    engine = _engine(tmp_path)
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
    assert "games" in inspect(engine).get_table_names()


def test_paused_and_dropped_statuses_are_converted(tmp_path):
    from alembic import command
    from backend.app.core.migrations import make_config
    engine = _engine(tmp_path)
    with engine.begin() as connection:
        command.upgrade(make_config(connection), "0004_genre_position")
        insert = ("insert into games (title, status, play_type, play_count, format, is_favorite, created_at, updated_at) "
                  "values (:t, :s, 'PRIMEIRA_JOGADA', 1, 'DIGITAL', 0, '2026-01-01', '2026-01-01')")
        for title, status in (("Pausado", "PAUSADO"), ("Largado", "DESISTI"), ("Normal", "ZERADO")):
            connection.execute(sa.text(insert), {"t": title, "s": status})
    run_migrations(engine)
    with engine.connect() as c:
        rows = dict(c.execute(sa.text("select title, status from games")).all())
    assert rows == {"Pausado": "FILA", "Largado": "DISPONIVEL", "Normal": "ZERADO"}


def test_upgrade_keeps_rows_that_depend_on_games(tmp_path):
    """Recriar/alterar `games` não pode apagar em cascata gêneros, vínculos de loja e pódios."""
    from alembic import command
    from backend.app.core import database
    from backend.app.core.migrations import make_config
    engine = _engine(tmp_path)
    sa.event.listen(engine, "connect", database._enable_sqlite_foreign_keys)  # como no app
    with engine.begin() as c:
        command.upgrade(make_config(c), "0006_yearbook_picks")
        c.execute(sa.text(
            "insert into games (id, title, status, play_type, play_count, format, is_favorite, created_at, updated_at) "
            "values (1, 'Hades', 'ZERADO', 'PRIMEIRA_JOGADA', 1, 'DIGITAL', 0, '2026-01-01', '2026-01-01')"))
        c.execute(sa.text("insert into genres (id, name, color) values (1, 'Roguelike', '#fff')"))
        c.execute(sa.text("insert into game_genres (game_id, genre_id, position) values (1, 1, 0)"))
        c.execute(sa.text("insert into game_store_links (game_id, store, external_id, created_at) values (1, 'steam', '1', '2026-01-01')"))
        c.execute(sa.text("insert into yearbook_picks (year, position, game_id) values (2026, 1, 1)"))
    run_migrations(engine)
    with engine.connect() as c:
        counts = [c.execute(sa.text(f"select count(*) from {t}")).scalar()
                  for t in ("games", "game_genres", "game_store_links", "yearbook_picks")]
        assert counts == [1, 1, 1, 1]
        assert c.exec_driver_sql("pragma foreign_keys").scalar() == 1  # religadas para o resto do app



def test_developer_text_becomes_a_link_before_the_column_is_dropped(tmp_path):
    from alembic import command
    from backend.app.core.migrations import make_config
    engine = _engine(tmp_path)
    with engine.begin() as c:
        command.upgrade(make_config(c), "0007_replay_links")
        c.execute(sa.text("insert into developers (id, name) values (1, 'Étude Studio')"))
        insert = ("insert into games (title, developer, developer_id, status, play_type, play_count, format, "
                  "is_favorite, created_at, updated_at) values (:t, :d, :i, 'FILA', 'PRIMEIRA_JOGADA', 1, "
                  "'DIGITAL', 0, '2026-01-01', '2026-01-01')")
        for title, dev, dev_id in (("A", "ÉTUDE STUDIO", None), ("B", " Nova ", None), ("C", "nova", None),
                                   ("D", "", None), ("E", "texto velho", 1)):
            c.execute(sa.text(insert), {"t": title, "d": dev, "i": dev_id})
    run_migrations(engine)
    with engine.connect() as c:
        links = dict(c.execute(sa.text("select title, developer_id from games")).fetchall())
        names = dict(c.execute(sa.text("select id, name from developers")).fetchall())
        columns = {col["name"] for col in inspect(engine).get_columns("games")}
    assert "developer" not in columns
    assert links["A"] == 1 and links["E"] == 1 and links["D"] is None
    assert links["B"] == links["C"] and names[links["B"]] == "Nova"   # um registro só, sem espaços
    assert len(names) == 2
