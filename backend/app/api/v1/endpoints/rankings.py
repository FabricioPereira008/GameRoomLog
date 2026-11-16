from typing import List

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.ranking import (
    GameRankingPosition, RankingCreate, RankingEntriesRequest, RankingOrderRequest, RankingResponse,
    RankingUpdate,
)
from backend.app.services.ranking_service import RankingService

router = APIRouter()


@router.get("/", response_model=List[RankingResponse])
def list_rankings(db: Session = Depends(get_db)):
    return RankingService.list_rankings(db)


@router.post("/", response_model=RankingResponse, status_code=status.HTTP_201_CREATED)
def create_ranking(payload: RankingCreate, db: Session = Depends(get_db)):
    return RankingService.create_ranking(db, payload)


@router.put("/order", response_model=List[RankingResponse])
def reorder_rankings(payload: RankingOrderRequest, db: Session = Depends(get_db)):
    return RankingService.reorder_rankings(db, payload.ranking_ids)


@router.get("/by-game/{game_id}", response_model=List[GameRankingPosition])
def rankings_for_game(game_id: int, db: Session = Depends(get_db)):
    return RankingService.rankings_for_game(db, game_id)


@router.get("/{ranking_id}", response_model=RankingResponse)
def get_ranking(ranking_id: int, db: Session = Depends(get_db)):
    return RankingService.get_ranking(db, ranking_id)


@router.put("/{ranking_id}", response_model=RankingResponse)
def update_ranking(ranking_id: int, payload: RankingUpdate, db: Session = Depends(get_db)):
    return RankingService.update_ranking(db, ranking_id, payload)


@router.delete("/{ranking_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ranking(ranking_id: int, db: Session = Depends(get_db)):
    RankingService.delete_ranking(db, ranking_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{ranking_id}/entries", response_model=RankingResponse)
def set_ranking_entries(ranking_id: int, payload: RankingEntriesRequest, db: Session = Depends(get_db)):
    return RankingService.set_entries(db, ranking_id, payload.game_ids)
