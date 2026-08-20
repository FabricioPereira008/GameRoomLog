from datetime import date
from backend.app.core.database import SessionLocal, engine, Base
from backend.app.models import Game, Genre, Platform, Franchise, GameStatus, PlayType, GameFormat

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Checa se já tem dados
    if db.query(Game).first():
        print("Banco de dados já contém registros. Seed ignorado.")
        db.close()
        return

    # Plataformas comuns do Notion
    platforms_data = [
        {"name": "PC", "icon_name": "pc"},
        {"name": "Switch 2", "icon_name": "switch"},
        {"name": "Nintendo Switch", "icon_name": "switch"},
        {"name": "3DS", "icon_name": "nintendo-3ds"},
        {"name": "Emulador", "icon_name": "gamepad"},
        {"name": "PlayStation 5", "icon_name": "playstation"},
    ]
    platforms = {}
    for p in platforms_data:
        plat = Platform(**p)
        db.add(plat)
        platforms[p["name"]] = plat

    # Gêneros
    genres_data = [
        {"name": "Plataforma", "color": "#4299E1"},
        {"name": "RPG", "color": "#9F7AEA"},
        {"name": "Ação/Aventura", "color": "#ED8936"},
        {"name": "Soulslike", "color": "#E53E3E"},
        {"name": "MetroidVania", "color": "#38B2AC"},
        {"name": "Exploração", "color": "#48BB78"},
        {"name": "Sandbox", "color": "#ECC94B"},
        {"name": "Puzzle", "color": "#667EEA"},
    ]
    genres = {}
    for g in genres_data:
        genre = Genre(**g)
        db.add(genre)
        genres[g["name"]] = genre

    # Franquias
    franchises_data = ["Super Mario", "The Legend of Zelda", "Monster Hunter", "Sonic"]
    franchises = {}
    for f in franchises_data:
        fran = Franchise(name=f)
        db.add(fran)
        franchises[f] = fran

    db.commit()

    # Jogos de exemplo baseados no Notion do usuário
    sample_games = [
        {
            "title": "Pokémon Pokopia",
            "developer": "Game Freak / Nintendo",
            "platform": platforms.get("Switch 2"),
            "genres": [genres.get("Sandbox")],
            "status": GameStatus.JOGANDO,
            "hltb_hours": 35.0,
            "played_hours": 12.0,
            "play_type": PlayType.PRIMEIRA_JOGADA
        },
        {
            "title": "Super Mario 64 DS",
            "developer": "Nintendo",
            "platform": platforms.get("3DS"),
            "franchise": franchises.get("Super Mario"),
            "genres": [genres.get("Plataforma")],
            "status": GameStatus.FILA,
            "hltb_hours": 14.0,
            "play_type": PlayType.PRIMEIRA_JOGADA
        },
        {
            "title": "Mario & Luigi: Brothership",
            "developer": "Nintendo",
            "platform": platforms.get("Switch 2"),
            "franchise": franchises.get("Super Mario"),
            "genres": [genres.get("RPG")],
            "status": GameStatus.FILA,
            "hltb_hours": 42.0,
            "play_type": PlayType.PRIMEIRA_JOGADA
        },
        {
            "title": "Mortal Shell",
            "developer": "Cold Symmetry",
            "platform": platforms.get("PC"),
            "genres": [genres.get("Soulslike")],
            "status": GameStatus.ZERADO,
            "hltb_hours": 8.0,
            "played_hours": 8.0,
            "score": 7.0,
            "difficulty": 7.0,
            "finish_date": date(2026, 2, 10),
            "completion_year": 2026,
            "play_type": PlayType.PRIMEIRA_JOGADA
        },
        {
            "title": "Zelda: Ocarina of Time",
            "developer": "Nintendo",
            "platform": platforms.get("3DS"),
            "franchise": franchises.get("The Legend of Zelda"),
            "genres": [genres.get("Ação/Aventura")],
            "status": GameStatus.PLATINADO,
            "hltb_hours": 30.0,
            "played_hours": 31.0,
            "score": 10.0,
            "difficulty": 6.0,
            "finish_date": date(2026, 1, 15),
            "platinum_date": date(2026, 1, 20),
            "completion_year": 2026,
            "play_type": PlayType.PRIMEIRA_JOGADA
        }
    ]

    for g_data in sample_games:
        game = Game(
            title=g_data["title"],
            developer=g_data.get("developer"),
            platform=g_data.get("platform"),
            franchise=g_data.get("franchise"),
            status=g_data["status"],
            hltb_hours=g_data.get("hltb_hours", 0.0),
            played_hours=g_data.get("played_hours", 0.0),
            score=g_data.get("score"),
            difficulty=g_data.get("difficulty"),
            finish_date=g_data.get("finish_date"),
            platinum_date=g_data.get("platinum_date"),
            completion_year=g_data.get("completion_year"),
            play_type=g_data.get("play_type", PlayType.PRIMEIRA_JOGADA)
        )
        if "genres" in g_data and g_data["genres"]:
            game.genres = [g for g in g_data["genres"] if g]
        db.add(game)

    db.commit()
    print("Seed concluído com sucesso!")
    db.close()

if __name__ == "__main__":
    seed()
