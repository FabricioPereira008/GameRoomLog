import sqlite3

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from backend.app.core.migrations import run_migrations
from backend.app.main import app
from backend.app.api.v1.endpoints import backups as backups_endpoint
from backend.app.services import backup_service as bs


def _engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'gameroom.db'}")
    run_migrations(engine)
    return engine


def _add_game(engine, title):
    with engine.begin() as c:
        c.execute(sa.text(
            "insert into games (title, status, play_type, play_count, format, is_favorite, created_at, updated_at) "
            "values (:t, 'FILA', 'PRIMEIRA_JOGADA', 1, 'DIGITAL', 0, '2026-01-01', '2026-01-01')"), {"t": title})


def _titles(engine):
    with engine.connect() as c:
        return sorted(r[0] for r in c.execute(sa.text("select title from games")))


def test_paths_and_memory_database(tmp_path):
    engine = _engine(tmp_path)
    assert bs.backup_dir(engine) == (tmp_path / "backups").resolve()
    memory = sa.create_engine("sqlite://")
    assert bs.backup_dir(memory) is None and bs.list_backups(memory) == []
    assert bs.auto_backup(memory) is None
    with pytest.raises(bs.InvalidBackupError):
        bs.create_backup(memory)


def test_auto_backup_once_a_day_and_skips_new_database(tmp_path):
    empty = sa.create_engine(f"sqlite:///{tmp_path / 'novo.db'}")
    assert bs.auto_backup(empty) is None  # banco novo, sem tabelas

    engine = _engine(tmp_path)
    _add_game(engine, "Hades")
    first = bs.auto_backup(engine)
    assert first["reason"] == "auto" and first["games_count"] == 1
    assert bs.auto_backup(engine) is None  # já tem backup hoje
    listed = bs.list_backups(engine)
    assert [b["name"] for b in listed] == [first["name"]] and listed[0]["reason_label"] == "Automático"


def test_rotation_keeps_the_newest(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    folder = bs.backup_dir(engine)
    folder.mkdir()
    for day in range(1, 13):
        (folder / f"gameroom-202601{day:02d}-120000.db").write_bytes(b"")
    (folder / "outro-arquivo.txt").write_text("não mexer")
    bs.create_backup(engine)
    names = sorted(p.name for p in folder.iterdir() if p.suffix == ".db")
    assert len(names) == bs.MAX_BACKUPS and "gameroom-20260101-120000.db" not in names
    assert (folder / "outro-arquivo.txt").exists()
    broken = [b for b in bs.list_backups(engine) if b["name"].startswith("gameroom-202601")]
    assert broken and broken[0]["games_count"] is None  # arquivo vazio: contagem desconhecida


def test_restore_replaces_data_saves_current_state_and_migrates(tmp_path):
    engine = _engine(tmp_path)
    _add_game(engine, "Antes")
    saved = bs.create_backup(engine)
    _add_game(engine, "Depois")
    migrated = []
    result = bs.restore_backup(engine, saved["name"], lambda e: migrated.append(e) or run_migrations(e))
    assert _titles(engine) == ["Antes"] and migrated == [engine]
    safety = next(b for b in bs.list_backups(engine) if b["name"] == result["safety_backup"])
    assert safety["reason"] == "antes-da-restauracao" and safety["games_count"] == 2

    with pytest.raises(bs.InvalidBackupError):
        bs.restore_backup(engine, "../gameroom.db", run_migrations)
    with pytest.raises(bs.BackupNotFoundError):
        bs.restore_backup(engine, "gameroom-20990101-000000.db", run_migrations)
    junk = bs.backup_dir(engine) / "gameroom-20200101-000000.db"
    junk.write_text("não é sqlite")
    with pytest.raises(bs.InvalidBackupError):
        bs.restore_backup(engine, junk.name, run_migrations)
    assert _titles(engine) == ["Antes"]


def test_restore_oldest_with_full_rotation_keeps_it_until_restored(tmp_path):
    engine = _engine(tmp_path)
    _add_game(engine, "Velho")
    oldest = bs.create_backup(engine)
    folder = bs.backup_dir(engine)
    for day in range(1, bs.MAX_BACKUPS):
        with sqlite3.connect(folder / f"gameroom-2099{day:04d}-000000.db") as c:
            c.execute("create table games (id integer)")
    _add_game(engine, "Novo")
    bs.restore_backup(engine, oldest["name"], run_migrations)
    assert _titles(engine) == ["Velho"]
    assert len([p for p in folder.iterdir() if bs.NAME_RE.match(p.name)]) == bs.MAX_BACKUPS


@pytest.fixture
def client(tmp_path):
    engine = _engine(tmp_path)
    _add_game(engine, "Hades")
    app.dependency_overrides[backups_endpoint.get_engine] = lambda: engine
    yield TestClient(app), engine
    app.dependency_overrides.pop(backups_endpoint.get_engine, None)


def test_backup_endpoints(client):
    http, engine = client
    empty = http.get("/api/v1/backups/").json()
    assert empty["backups"] == [] and empty["max_backups"] == bs.MAX_BACKUPS and empty["folder"].endswith("backups")
    created = http.post("/api/v1/backups/")
    assert created.status_code == 201 and created.json()["reason"] == "manual"
    _add_game(engine, "Celeste")
    restored = http.post(f"/api/v1/backups/{created.json()['name']}/restore")
    assert restored.status_code == 200 and _titles(engine) == ["Hades"]
    assert len(http.get("/api/v1/backups/").json()["backups"]) == 2
    assert http.post("/api/v1/backups/gameroom-20990101-000000.db/restore").status_code == 404
    assert http.post("/api/v1/backups/qualquer.db/restore").status_code == 400

    app.dependency_overrides[backups_endpoint.get_engine] = lambda: sa.create_engine("sqlite://")
    assert http.post("/api/v1/backups/").status_code == 400


def test_lifespan_backs_up_before_migrating(tmp_path, monkeypatch):
    from backend.app import main
    engine = _engine(tmp_path)
    _add_game(engine, "Hades")
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app):
        pass
    assert [b["reason"] for b in bs.list_backups(engine)] == ["auto"]
