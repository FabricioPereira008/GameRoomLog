import json
from datetime import date
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.game import Game, GameStatus, PlayType
from backend.app.models.inbox import InboxEvent
from backend.app.models.platform import Platform
from backend.app.services.inbox_service import match_key, propose_state, similarity

CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "contracts"

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


def add_game(db, title, platform=None, **kw):
    plat = None
    if platform:
        plat = db.query(Platform).filter_by(name=platform).first() or Platform(name=platform)
        db.add(plat)
        db.flush()
    game = Game(title=title, platform_id=plat.id if plat else None, **kw)
    db.add(game)
    db.commit()
    return game


def ev(uid, type_, title, platform=None, day="2026-10-12", **kw):
    return {"id": uid, "type": type_, "title": title, "platform": platform, "date": day, **kw}


def package(*events, version=1):
    return {"format": "gameroom-inbox", "version": version, "events": list(events)}


def post(*events, **kw):
    return client.post("/api/v1/inbox/import", json=package(*events, **kw))


def pending(threshold=None):
    params = {"threshold": threshold} if threshold else {}
    r = client.get("/api/v1/inbox/pending", params=params)
    assert r.status_code == 200
    return r.json()


def fake_event(type_, day, **kw):
    """InboxEvent fora do banco, para testar as regras de proposta isoladamente."""
    return InboxEvent(event_type=type_, event_date=day, title="x", uuid=f"{type_}{day}", **kw)


# --- contrato ---

@pytest.mark.parametrize("schema, example", [
    ("gameroom-inbox.v1.schema.json", "inbox-v1.json"),
    ("gameroom-catalog.v1.schema.json", "catalog-v1.json"),
])
def test_contract_examples_match_schema(schema, example):
    jsonschema.validate(
        json.loads((CONTRACTS / "examples" / example).read_text(encoding="utf-8")),
        json.loads((CONTRACTS / schema).read_text(encoding="utf-8")),
    )


def test_contract_example_is_accepted_by_import():
    data = json.loads((CONTRACTS / "examples" / "inbox-v1.json").read_text(encoding="utf-8"))
    r = client.post("/api/v1/inbox/import", json=data)
    assert r.status_code == 200
    assert r.json() == {"received": 3, "imported": 3, "duplicates": 0, "rejected": []}


def test_catalog_endpoint_matches_schema(db):
    add_game(db, "Celeste", "PC", status=GameStatus.JOGANDO)
    add_game(db, "Sem Plataforma")
    r = client.get("/api/v1/inbox/catalog")
    assert r.status_code == 200
    body = r.json()
    jsonschema.validate(body, json.loads((CONTRACTS / "gameroom-catalog.v1.schema.json").read_text(encoding="utf-8")))
    assert [g["title"] for g in body["games"]] == ["Celeste", "Sem Plataforma"]
    assert body["games"][0] == {"id": body["games"][0]["id"], "title": "Celeste", "platform": "PC", "status": "Jogando"}
    assert body["platforms"] == ["PC"]


# --- importação ---

def test_import_is_idempotent_by_uuid():
    first = post(ev("a", "finished", "Hollow Knight"), ev("b", "playing", "Celeste"))
    assert first.json()["imported"] == 2
    again = post(ev("a", "finished", "Hollow Knight"), ev("c", "platinum", "Celeste"))
    assert again.json() == {"received": 2, "imported": 1, "duplicates": 1, "rejected": []}
    assert pending()["total_events"] == 3


def test_duplicate_uuid_inside_same_package_is_counted_once():
    r = post(ev("a", "finished", "X"), ev("a", "finished", "X"))
    assert r.json()["imported"] == 1 and r.json()["duplicates"] == 1


def test_invalid_event_is_rejected_without_dropping_others():
    r = post(ev("ok", "finished", "Celeste"), ev("bad", "finished", "Hades", score=11), {"id": "x", "type": "conquista", "title": "Y"})
    body = r.json()
    assert body["imported"] == 1
    assert len(body["rejected"]) == 2
    assert "Hades" in body["rejected"][0] and "score" in body["rejected"][0]


def test_unknown_fields_are_ignored():
    r = client.post("/api/v1/inbox/import", json={**package(ev("a", "finished", "X", mood="feliz")), "device": "Odin 2"})
    assert r.status_code == 200 and r.json()["imported"] == 1


def test_newer_version_is_refused():
    r = post(ev("a", "finished", "X"), version=2)
    assert r.status_code == 422
    assert "Versão 2" in r.json()["detail"]


@pytest.mark.parametrize("payload", [
    {"format": "outro", "version": 1, "events": []},
    {"format": "gameroom-inbox", "events": []},
    {"format": "gameroom-inbox", "version": 1},
])
def test_malformed_envelope_returns_422(payload):
    assert client.post("/api/v1/inbox/import", json=payload).status_code == 422


def test_missing_date_uses_created_at_date():
    post({"id": "a", "type": "finished", "title": "X", "created_at": "2026-09-30T23:30:00-03:00"})
    event = pending()["groups"][0]["events"][0]
    assert event["event_date"] == "2026-10-01"  # convertido para UTC


def test_missing_date_and_created_at_uses_today():
    post({"id": "a", "type": "finished", "title": "X"})
    assert pending()["groups"][0]["events"][0]["event_date"] == date.today().isoformat()


# --- correspondência ---

def test_match_key_normalizes_roman_numerals_and_article():
    assert match_key("The Witcher III: Wild Hunt") == match_key("Witcher 3 - Wild Hunt")
    assert similarity(match_key("Square Enix"), match_key("SquareEnix")) == 100


def test_exact_title_match_links_directly(db):
    game = add_game(db, "Hollow Knight", "Nintendo Switch", status=GameStatus.FILA)
    post(ev("a", "finished", "hollow knight", "Nintendo Switch", played_hours=38, score=9))
    group = pending()["groups"][0]
    assert group["match"] == "exact"
    cand = group["candidates"][0]
    assert cand["game_id"] == game.id and cand["similarity"] == 100 and cand["platform_matches"]
    assert cand["current"]["status"] == "Fila"
    assert cand["changes"] == {"status": "Zerado", "finish_date": "2026-10-12", "played_hours": 38.0, "score": 9.0}


def test_game_id_from_catalog_takes_precedence(db):
    game = add_game(db, "Nome totalmente diferente")
    post(ev("a", "finished", "Celeste", game_id=game.id))
    group = pending()["groups"][0]
    assert group["key"] == f"id:{game.id}" and group["match"] == "exact"
    assert group["candidates"][0]["game_id"] == game.id


def test_unknown_game_id_falls_back_to_title(db):
    game = add_game(db, "Celeste")
    post(ev("a", "finished", "Celeste", game_id=999))
    group = pending()["groups"][0]
    assert group["match"] == "exact" and group["candidates"][0]["game_id"] == game.id


def test_similar_title_asks_for_confirmation(db):
    add_game(db, "Hollow Knight")
    add_game(db, "Hollow Knight: Silksong")
    add_game(db, "Celeste")
    post(ev("a", "finished", "Holow Knight"))
    group = pending()["groups"][0]
    assert group["match"] == "confirm"
    titles = [c["title"] for c in group["candidates"]]
    assert titles[0] == "Hollow Knight" and "Celeste" not in titles
    assert all(85 <= c["similarity"] < 100 for c in group["candidates"])


def test_threshold_is_configurable(db):
    add_game(db, "Hollow Knight")
    post(ev("a", "finished", "Holow Knight"))
    assert pending(threshold=99)["groups"][0]["match"] == "none"


def test_no_match_offers_new_game_payload(db):
    add_game(db, "Celeste")
    post(ev("a", "playing", "Dead Cells", "Android", day="2026-10-01"),
         ev("b", "finished", "Dead Cells", "Android", played_hours=20, notes="Muito bom"))
    group = pending()["groups"][0]
    assert group["match"] == "none" and group["candidates"] == []
    assert len(group["events"]) == 2
    assert group["platform_match"] == {"platform_id": None, "name": "Android", "similarity": 0, "is_new": True}
    new = group["new_game"]
    assert new["title"] == "Dead Cells" and new["status"] == "Zerado" and new["finish_date"] == "2026-10-12"
    assert new["played_hours"] == 20.0 and new["notes"] == "[Portátil 12/10/2026] Muito bom"
    assert "platform_id" not in new


def test_platform_is_matched_ignoring_spaces_and_used_as_tiebreaker(db):
    add_game(db, "Celeste", "PC")
    switch_game = add_game(db, "Celeste", "Nintendo Switch")
    post(ev("a", "finished", "Celeste", "NintendoSwitch"))
    group = pending()["groups"][0]
    assert group["platform_match"]["platform_id"] == switch_game.platform_id
    assert group["match"] == "exact"
    assert group["candidates"][0]["game_id"] == switch_game.id
    assert group["new_game"]["platform_id"] == switch_game.platform_id


def test_same_title_on_other_platforms_needs_confirmation(db):
    add_game(db, "Celeste", "PC")
    add_game(db, "Celeste", "PS4")
    post(ev("a", "finished", "Celeste", "Android"))
    group = pending()["groups"][0]
    assert group["match"] == "confirm"
    assert not any(c["platform_matches"] for c in group["candidates"])


def test_single_exact_title_on_other_platform_links_with_warning(db):
    add_game(db, "Celeste", "PC")
    post(ev("a", "finished", "Celeste", "Android"))
    group = pending()["groups"][0]
    assert group["match"] == "exact" and group["candidates"][0]["platform_matches"] is False


def test_events_are_grouped_per_title_and_platform():
    post(ev("a", "playing", "Celeste", "Android"), ev("b", "finished", "celeste", "android"),
         ev("c", "finished", "Celeste", "PC"))
    groups = pending()["groups"]
    assert sorted(len(g["events"]) for g in groups) == [1, 2]


# --- regras de proposta ---

def test_playing_on_finished_game_starts_replay_without_counting():
    game = Game(title="x", status=GameStatus.ZERADO, finish_date=date(2023, 1, 1), play_type=PlayType.PRIMEIRA_JOGADA, play_count=1)
    state = propose_state(game, [fake_event("playing", date(2026, 10, 1))])
    assert state["status"] == GameStatus.JOGANDO
    assert state["play_type"] == PlayType.REJOGADA and state["play_count"] == 1


def test_playing_then_finished_counts_replay_once():
    game = Game(title="x", status=GameStatus.ZERADO, finish_date=date(2023, 1, 1), play_type=PlayType.PRIMEIRA_JOGADA, play_count=1)
    state = propose_state(game, [fake_event("finished", date(2026, 10, 12)), fake_event("playing", date(2026, 10, 1))])
    assert state["status"] == GameStatus.ZERADO and state["finish_date"] == date(2026, 10, 12)
    assert state["play_type"] == PlayType.REJOGADA and state["play_count"] == 2


def test_finished_with_other_date_on_finished_game_is_replay():
    game = Game(title="x", status=GameStatus.ZERADO, finish_date=date(2023, 1, 1), play_count=1)
    state = propose_state(game, [fake_event("finished", date(2026, 10, 12))])
    assert state["play_count"] == 2 and state["play_type"] == PlayType.REJOGADA


def test_finished_with_same_date_is_not_replay():
    game = Game(title="x", status=GameStatus.ZERADO, finish_date=date(2026, 10, 12), play_count=1)
    state = propose_state(game, [fake_event("finished", date(2026, 10, 12), score=8)])
    assert state["play_count"] == 1 and state["score"] == 8


def test_platinum_without_finish_date_proposes_same_date():
    game = Game(title="x", status=GameStatus.JOGANDO, play_count=1)
    state = propose_state(game, [fake_event("platinum", date(2026, 10, 15))])
    assert state["status"] == GameStatus.PLATINADO
    assert state["finish_date"] == state["platinum_date"] == date(2026, 10, 15)


def test_platinum_keeps_existing_finish_date():
    game = Game(title="x", status=GameStatus.ZERADO, finish_date=date(2026, 9, 1), play_count=1)
    state = propose_state(game, [fake_event("platinum", date(2026, 10, 15))])
    assert state["finish_date"] == date(2026, 9, 1) and state["play_count"] == 1


def test_replay_on_platinum_game_keeps_platinum_status():
    game = Game(title="x", status=GameStatus.PLATINADO, finish_date=date(2023, 1, 1), platinum_date=date(2023, 2, 1), play_count=1)
    state = propose_state(game, [fake_event("playing", date(2026, 10, 1)), fake_event("finished", date(2026, 10, 12))])
    assert state["status"] == GameStatus.PLATINADO and state["play_count"] == 2


def test_finished_and_platinum_in_same_replay_count_once():
    game = Game(title="x", status=GameStatus.PLATINADO, finish_date=date(2023, 1, 1), platinum_date=date(2023, 2, 1), play_count=1)
    state = propose_state(game, [fake_event("finished", date(2026, 10, 12)), fake_event("platinum", date(2026, 10, 20))])
    assert state["play_count"] == 2 and state["platinum_date"] == date(2026, 10, 20)


def test_last_reported_stats_win_and_notes_accumulate():
    game = Game(title="x", status=GameStatus.JOGANDO, played_hours=5.0, notes="Antigo", play_count=1)
    state = propose_state(game, [
        fake_event("playing", date(2026, 10, 1), played_hours=10, notes="Começo"),
        fake_event("finished", date(2026, 10, 12), played_hours=30, difficulty=7),
    ])
    assert state["played_hours"] == 30 and state["difficulty"] == 7
    assert state["notes"] == "Antigo\n[Portátil 01/10/2026] Começo"


# --- resolução ---

def test_resolve_applied_removes_from_pending(db):
    game = add_game(db, "Celeste")
    post(ev("a", "finished", "Celeste"), ev("b", "finished", "Hades"))
    ids = [e["id"] for g in pending()["groups"] if g["title"] == "Celeste" for e in g["events"]]
    r = client.post("/api/v1/inbox/resolve", json={"event_ids": ids, "action": "applied", "game_id": game.id})
    assert r.status_code == 200 and r.json() == {"resolved": 1}
    remaining = pending()
    assert remaining["total_events"] == 1 and remaining["groups"][0]["title"] == "Hades"
    stored = db.query(InboxEvent).filter_by(uuid="a").one()
    assert stored.status == "applied" and stored.applied_game_id == game.id and stored.resolved_at


def test_resolved_events_are_not_reimported():
    post(ev("a", "finished", "Celeste"))
    ids = [e["id"] for e in pending()["groups"][0]["events"]]
    client.post("/api/v1/inbox/resolve", json={"event_ids": ids, "action": "discarded"})
    assert post(ev("a", "finished", "Celeste")).json()["duplicates"] == 1
    assert pending()["total_events"] == 0


def test_resolve_twice_only_counts_pending():
    post(ev("a", "finished", "Celeste"))
    ids = [e["id"] for e in pending()["groups"][0]["events"]]
    client.post("/api/v1/inbox/resolve", json={"event_ids": ids, "action": "discarded"})
    r = client.post("/api/v1/inbox/resolve", json={"event_ids": ids, "action": "applied"})
    assert r.json() == {"resolved": 0}


def test_resolve_unknown_ids_returns_404():
    assert client.post("/api/v1/inbox/resolve", json={"event_ids": [999], "action": "applied"}).status_code == 404


@pytest.mark.parametrize("payload", [
    {"event_ids": [], "action": "applied"},
    {"event_ids": [1], "action": "apagar"},
])
def test_resolve_validation(payload):
    assert client.post("/api/v1/inbox/resolve", json=payload).status_code == 422


def test_pending_threshold_validation():
    assert client.get("/api/v1/inbox/pending", params={"threshold": 10}).status_code == 422


def test_pending_empty():
    assert pending() == {"total_events": 0, "groups": []}


def test_proposal_for_manually_chosen_game(db):
    game = add_game(db, "Hollow Knight", status=GameStatus.FILA)
    post(ev("a", "finished", "HK", played_hours=40))
    ids = [e["id"] for e in pending()["groups"][0]["events"]]
    r = client.post("/api/v1/inbox/proposal", json={"event_ids": ids, "game_id": game.id})
    assert r.status_code == 200
    body = r.json()
    assert body["game_id"] == game.id and body["changes"]["status"] == "Zerado"
    assert body["changes"]["played_hours"] == 40.0


def test_proposal_404s(db):
    game = add_game(db, "Celeste")
    post(ev("a", "finished", "Celeste"))
    ids = [e["id"] for e in pending()["groups"][0]["events"]]
    assert client.post("/api/v1/inbox/proposal", json={"event_ids": ids, "game_id": 999}).status_code == 404
    assert client.post("/api/v1/inbox/proposal", json={"event_ids": [999], "game_id": game.id}).status_code == 404


# --- rejogadas como novo registro vinculado ---

def _finished_game(db, title="Hades", **kw):
    from backend.app.models.developer import Developer
    from backend.app.models.genre import Genre
    genre, dev = Genre(name="Roguelike"), Developer(name="Supergiant")
    db.add_all([genre, dev])
    db.flush()
    game = add_game(db, title, "PC", status=GameStatus.ZERADO, finish_date=date(2023, 1, 1),
                    play_type=PlayType.PRIMEIRA_JOGADA, play_count=1, developer_id=dev.id,
                    cover_image="hades.jpg", **kw)
    game.genres = [genre]
    db.commit()
    return game


def test_playing_a_finished_game_proposes_a_linked_replay(db):
    game = _finished_game(db)
    post(ev("a", "playing", "Hades", "PC", day="2026-10-01", played_hours=3))
    cand = pending()["groups"][0]["candidates"][0]
    assert cand["game_id"] == game.id and cand["changes"] == {}  # o registro antigo fica intacto
    replay = cand["replay"]
    assert replay["replay_of_id"] == game.id and replay["play_type"] == "Rejogada" and replay["play_count"] == 2
    assert replay["status"] == "Jogando" and replay["played_hours"] == 3.0
    assert replay["title"] == "Hades" and replay["platform_id"] == game.platform_id
    assert replay["developer"] == "Supergiant" and replay["cover_image"] == "hades.jpg"
    assert replay["genre_ids"] == [g.id for g in game.genres]
    assert "finish_date" not in replay


def test_finishing_again_with_new_date_proposes_finished_replay(db):
    _finished_game(db)
    post(ev("a", "finished", "Hades", "PC", day="2026-10-12", score=10))
    cand = pending()["groups"][0]["candidates"][0]
    assert cand["changes"] == {}
    assert cand["replay"]["status"] == "Zerado" and cand["replay"]["finish_date"] == "2026-10-12"
    assert cand["replay"]["score"] == 10.0


def test_events_before_the_replay_still_update_the_original(db):
    _finished_game(db)
    post(ev("a", "platinum", "Hades", "PC", day="2026-01-05"), ev("b", "playing", "Hades", "PC", day="2026-10-01"))
    cand = pending()["groups"][0]["candidates"][0]
    assert cand["changes"]["status"] == "Platinado" and cand["changes"]["platinum_date"] == "2026-01-05"
    assert cand["replay"]["status"] == "Jogando"


def test_replay_in_progress_receives_the_next_events(db):
    original = _finished_game(db)
    current = add_game(db, "Hades", "PC", status=GameStatus.JOGANDO, play_type=PlayType.REJOGADA,
                       play_count=2, replay_of_id=original.id)
    post(ev("a", "finished", "Hades", "PC", day="2026-10-20"))
    group = pending()["groups"][0]
    assert group["match"] == "exact" and len(group["candidates"]) == 1  # o grupo conta como um jogo só
    cand = group["candidates"][0]
    assert cand["game_id"] == current.id and cand["replay"] is None
    assert cand["changes"] == {"status": "Zerado", "finish_date": "2026-10-20"}


def test_catalog_game_id_of_the_original_goes_to_the_latest_play(db):
    original = _finished_game(db)
    current = add_game(db, "Hades", "PC", status=GameStatus.JOGANDO, play_type=PlayType.REJOGADA,
                       play_count=2, replay_of_id=original.id)
    post(ev("a", "finished", "Hades", "PC", day="2026-10-20", game_id=original.id))
    assert pending()["groups"][0]["candidates"][0]["game_id"] == current.id


def test_third_play_links_to_the_first_record(db):
    original = _finished_game(db)
    add_game(db, "Hades", "PC", status=GameStatus.ZERADO, finish_date=date(2024, 6, 1),
             play_type=PlayType.REJOGADA, play_count=2, replay_of_id=original.id)
    post(ev("a", "playing", "Hades", "PC", day="2026-10-01"))
    replay = pending()["groups"][0]["candidates"][0]["replay"]
    assert replay["replay_of_id"] == original.id and replay["play_count"] == 3


def test_manual_proposal_uses_the_latest_play(db):
    original = _finished_game(db)
    current = add_game(db, "Hades", "PC", status=GameStatus.JOGANDO, play_type=PlayType.REJOGADA,
                       play_count=2, replay_of_id=original.id)
    post(ev("a", "finished", "Outro nome", day="2026-10-20"))
    ids = [e["id"] for e in pending()["groups"][0]["events"]]
    r = client.post("/api/v1/inbox/proposal", json={"event_ids": ids, "game_id": original.id})
    assert r.status_code == 200 and r.json()["game_id"] == current.id and r.json()["replay"] is None


def test_catalog_lists_each_group_of_plays_once(db):
    original = _finished_game(db)
    latest = add_game(db, "Hades", "PC", status=GameStatus.JOGANDO, play_type=PlayType.REJOGADA,
                      play_count=2, replay_of_id=original.id)
    add_game(db, "Celeste")
    games = client.get("/api/v1/inbox/catalog").json()["games"]
    assert [(g["title"], g["id"]) for g in games] == [("Celeste", games[0]["id"]), ("Hades", latest.id)]


def test_status_and_type_are_stored_as_plain_text(db):
    from sqlalchemy import text
    post(ev("a", "finished", "Celeste"))
    event_id = pending()["groups"][0]["events"][0]["id"]
    assert db.execute(text("select status, event_type from inbox_events")).one() == ("pending", "finished")
    client.post("/api/v1/inbox/resolve", json={"event_ids": [event_id], "action": "applied", "game_id": None})
    db.expire_all()
    assert db.execute(text("select status from inbox_events")).scalar() == "applied"
