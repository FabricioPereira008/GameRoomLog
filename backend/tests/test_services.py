import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.core.database import Base
from backend.app.models.game import GameStatus, PlayType
from backend.app.models.platform import Platform
from backend.app.models.genre import Genre
from backend.app.models.franchise import Franchise
from backend.app.models.developer import Developer
from backend.app.schemas.game import GameCreate, GameUpdate
from backend.app.services.game_service import GameService
from backend.app.services.stats_service import StatsService

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_game_service_create_and_auto_completion_year(db):
    # Test auto completion_year from finish_date
    g1 = GameService.create_game(db, GameCreate(
        title="Elden Ring",
        status=GameStatus.ZERADO,
        finish_date=date(2025, 5, 20),
        developer="FromSoftware"
    ))
    assert g1.id is not None
    assert g1.completion_year == 2025
    assert g1.developer == "FromSoftware"
    assert g1.developer_id is not None  # Auto-created developer entity

    # Test auto completion_year from platinum_date
    g2 = GameService.create_game(db, GameCreate(
        title="Bloodborne",
        status=GameStatus.PLATINADO,
        platinum_date=date(2024, 11, 10),
        developer="FromSoftware"
    ))
    assert g2.completion_year == 2024
    # Check that developer ID is reused
    assert g2.developer_id == g1.developer_id

def test_game_service_genre_associations(db):
    genre1 = Genre(name="Soulslike", color="#111111")
    genre2 = Genre(name="Action RPG", color="#222222")
    db.add_all([genre1, genre2])
    db.commit()

    game = GameService.create_game(db, GameCreate(
        title="Dark Souls III",
        status=GameStatus.ZERADO,
        genre_ids=[genre1.id, genre2.id]
    ))
    assert len(game.genres) == 2

    # Update genres (remove one, keep one)
    updated = GameService.update_game(db, game.id, GameUpdate(
        genre_ids=[genre2.id]
    ))
    assert len(updated.genres) == 1
    assert updated.genres[0].name == "Action RPG"

def test_game_service_filtering_and_sorting(db):
    p1 = Platform(name="PS5", icon_name="playstation")
    p2 = Platform(name="PC", icon_name="pc")
    g_rpg = Genre(name="RPG", color="#E53E3E")
    g_indie = Genre(name="Indie", color="#38A169")
    db.add_all([p1, p2, g_rpg, g_indie])
    db.commit()

    GameService.create_game(db, GameCreate(
        title="The Witcher 3",
        status=GameStatus.ZERADO,
        platform_id=p2.id,
        genre_ids=[g_rpg.id],
        score=10.0,
        hltb_hours=50.0,
        completion_year=2024
    ))
    GameService.create_game(db, GameCreate(
        title="Hades",
        status=GameStatus.PLATINADO,
        platform_id=p2.id,
        genre_ids=[g_indie.id],
        score=9.5,
        hltb_hours=20.0,
        completion_year=2024
    ))
    GameService.create_game(db, GameCreate(
        title="God of War Ragnarok",
        status=GameStatus.FILA,
        platform_id=p1.id,
        genre_ids=[g_rpg.id],
        score=9.0,
        hltb_hours=35.0
    ))

    # Filter by status
    zerados = GameService.get_games(db, status=GameStatus.ZERADO)
    assert len(zerados) == 1
    assert zerados[0].title == "The Witcher 3"

    # Filter by platform
    pc_games = GameService.get_games(db, platform_id=p2.id)
    assert len(pc_games) == 2

    # Filter by genre
    indie_games = GameService.get_games(db, genre_id=g_indie.id)
    assert len(indie_games) == 1
    assert indie_games[0].title == "Hades"

    # Search filter
    searched = GameService.get_games(db, search="Ragnarok")
    assert len(searched) == 1
    assert searched[0].title == "God of War Ragnarok"

    # Sort by HLTB asc
    sorted_hltb = GameService.get_games(db, sort_by="hltb_asc")
    assert sorted_hltb[0].title == "Hades"
    assert sorted_hltb[-1].title == "The Witcher 3"

    # Sort by Score desc
    sorted_score = GameService.get_games(db, sort_by="score_desc")
    assert sorted_score[0].title == "The Witcher 3"

def test_stats_service_overall_and_yearbook(db):
    GameService.create_game(db, GameCreate(
        title="Celeste",
        status=GameStatus.ZERADO,
        played_hours=15.0,
        finish_date=date(2025, 1, 1),
        score=9.0
    ))
    GameService.create_game(db, GameCreate(
        title="Hollow Knight",
        status=GameStatus.PLATINADO,
        played_hours=45.0,
        finish_date=date(2025, 2, 1),
        platinum_date=date(2025, 2, 5),
        score=10.0
    ))

    overall = StatsService.get_overall_stats(db)
    assert overall.status_counts.total == 2
    assert overall.status_counts.zerados == 1
    assert overall.status_counts.platinados == 1
    assert overall.total_hours == 60.0

    yearbook_2025 = StatsService.get_yearbook(db, 2025)
    assert yearbook_2025.total_games_finished == 2
    assert yearbook_2025.total_platinums == 1
    assert yearbook_2025.total_hours_played == 60.0
    assert yearbook_2025.average_score == 9.5
