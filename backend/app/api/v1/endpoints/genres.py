from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.models.genre import Genre
from backend.app.models.game import Game, game_genres
from backend.app.schemas.genre import GenreCreate, GenreUpdate, GenreResponse
from backend.app.schemas.category_detail import CategoryDetailResponse
from backend.app.schemas.game import GameResponse

router = APIRouter()

@router.get("/", response_model=List[GenreResponse])
def list_genres(db: Session = Depends(get_db)):
    genres = db.query(Genre).order_by(Genre.name.asc()).all()
    results = []
    for g in genres:
        count = db.query(func.count(game_genres.c.game_id)).filter(game_genres.c.genre_id == g.id).scalar() or 0
        resp = GenreResponse.model_validate(g)
        resp.games_count = count
        results.append(resp)
    return results

@router.get("/{genre_id}/details", response_model=CategoryDetailResponse)
def get_genre_details(genre_id: int, db: Session = Depends(get_db)):
    genre = db.query(Genre).filter(Genre.id == genre_id).first()
    if not genre:
        raise HTTPException(status_code=404, detail="Gênero não encontrado")

    games = db.query(Game).filter(Game.genres.any(Genre.id == genre_id)).order_by(Game.title.asc()).all()
    total_hours = sum(g.played_hours or g.hltb_hours or 0.0 for g in games)

    return CategoryDetailResponse(
        id=genre.id,
        name=genre.name,
        category_type="genre",
        color=genre.color,
        total_games=len(games),
        total_hours_played=round(total_hours, 1),
        games=[GameResponse.model_validate(g) for g in games]
    )

@router.post("/", response_model=GenreResponse, status_code=status.HTTP_201_CREATED)
def create_genre(genre_in: GenreCreate, db: Session = Depends(get_db)):
    existing = db.query(Genre).filter(Genre.name.ilike(genre_in.name.strip())).first()
    if existing:
        return existing
    db_genre = Genre(name=genre_in.name.strip(), color=genre_in.color or "#4f46e5")
    db.add(db_genre)
    db.commit()
    db.refresh(db_genre)
    return db_genre

@router.put("/{genre_id}", response_model=GenreResponse)
def update_genre(genre_id: int, genre_in: GenreUpdate, db: Session = Depends(get_db)):
    db_genre = db.query(Genre).filter(Genre.id == genre_id).first()
    if not db_genre:
        raise HTTPException(status_code=404, detail="Gênero não encontrado")
    if genre_in.name is not None:
        db_genre.name = genre_in.name.strip()
    if genre_in.color is not None:
        db_genre.color = genre_in.color
    db.commit()
    db.refresh(db_genre)
    count = db.query(func.count(game_genres.c.game_id)).filter(game_genres.c.genre_id == db_genre.id).scalar() or 0
    resp = GenreResponse.model_validate(db_genre)
    resp.games_count = count
    return resp

@router.delete("/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_genre(genre_id: int, db: Session = Depends(get_db)):
    db_genre = db.query(Genre).filter(Genre.id == genre_id).first()
    if not db_genre:
        raise HTTPException(status_code=404, detail="Gênero não encontrado")
    db.delete(db_genre)
    db.commit()
