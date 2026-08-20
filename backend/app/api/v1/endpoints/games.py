from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.game import GameStatus
from backend.app.schemas.game import GameCreate, GameUpdate, GameResponse
from backend.app.services.game_service import GameService

router = APIRouter()

@router.get("/", response_model=List[GameResponse])
def list_games(
    status: Optional[GameStatus] = None,
    platform_id: Optional[int] = None,
    genre_id: Optional[int] = None,
    franchise_id: Optional[int] = None,
    completion_year: Optional[int] = None,
    is_favorite: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = Query("title_asc", description="title_asc, title_desc, score_desc, hltb_asc, finish_date_desc, recent"),
    db: Session = Depends(get_db)
):
    return GameService.get_games(
        db=db,
        status=status,
        platform_id=platform_id,
        genre_id=genre_id,
        franchise_id=franchise_id,
        completion_year=completion_year,
        is_favorite=is_favorite,
        search=search,
        sort_by=sort_by
    )

@router.post("/", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
def create_game(game_in: GameCreate, db: Session = Depends(get_db)):
    return GameService.create_game(db=db, game_in=game_in)

@router.get("/{game_id}", response_model=GameResponse)
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = GameService.get_game_by_id(db=db, game_id=game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    return game

@router.put("/{game_id}", response_model=GameResponse)
def update_game(game_id: int, game_in: GameUpdate, db: Session = Depends(get_db)):
    game = GameService.update_game(db=db, game_id=game_id, game_in=game_in)
    if not game:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    return game

@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(game_id: int, db: Session = Depends(get_db)):
    success = GameService.delete_game(db=db, game_id=game_id)
    if not success:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
