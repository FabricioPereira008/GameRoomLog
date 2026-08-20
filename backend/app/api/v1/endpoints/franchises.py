from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.models.franchise import Franchise
from backend.app.models.game import Game, GameStatus
from backend.app.schemas.franchise import FranchiseCreate, FranchiseUpdate, FranchiseResponse
from backend.app.schemas.category_detail import CategoryDetailResponse
from backend.app.schemas.game import GameResponse

router = APIRouter()

@router.get("/", response_model=List[FranchiseResponse])
def list_franchises(db: Session = Depends(get_db)):
    franchises = db.query(Franchise).order_by(Franchise.name.asc()).all()
    results = []
    for f in franchises:
        count = db.query(func.count(Game.id)).filter(
            Game.franchise_id == f.id,
            Game.status.in_([GameStatus.ZERADO, GameStatus.PLATINADO])
        ).scalar() or 0
        resp = FranchiseResponse.model_validate(f)
        resp.games_count = count
        results.append(resp)
    return results

@router.get("/{franchise_id}/details", response_model=CategoryDetailResponse)
def get_franchise_details(franchise_id: int, db: Session = Depends(get_db)):
    franchise = db.query(Franchise).filter(Franchise.id == franchise_id).first()
    if not franchise:
        raise HTTPException(status_code=404, detail="Franquia não encontrada")

    # Apenas jogos zerados ou platinados
    games = db.query(Game).filter(
        Game.franchise_id == franchise_id,
        Game.status.in_([GameStatus.ZERADO, GameStatus.PLATINADO])
    ).order_by(Game.finish_date.desc().nullslast(), Game.title.asc()).all()
    
    total_hours = sum(g.played_hours or g.hltb_hours or 0.0 for g in games)

    return CategoryDetailResponse(
        id=franchise.id,
        name=franchise.name,
        category_type="franchise",
        total_games=len(games),
        total_hours_played=round(total_hours, 1),
        games=[GameResponse.model_validate(g) for g in games]
    )

@router.post("/", response_model=FranchiseResponse, status_code=status.HTTP_201_CREATED)
def create_franchise(franchise_in: FranchiseCreate, db: Session = Depends(get_db)):
    existing = db.query(Franchise).filter(Franchise.name.ilike(franchise_in.name.strip())).first()
    if existing:
        return existing
    db_franchise = Franchise(name=franchise_in.name.strip())
    db.add(db_franchise)
    db.commit()
    db.refresh(db_franchise)
    return db_franchise

@router.put("/{franchise_id}", response_model=FranchiseResponse)
def update_franchise(franchise_id: int, franchise_in: FranchiseUpdate, db: Session = Depends(get_db)):
    db_franchise = db.query(Franchise).filter(Franchise.id == franchise_id).first()
    if not db_franchise:
        raise HTTPException(status_code=404, detail="Franquia não encontrada")
    if franchise_in.name is not None:
        db_franchise.name = franchise_in.name.strip()
    db.commit()
    db.refresh(db_franchise)
    return db_franchise

@router.delete("/{franchise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_franchise(franchise_id: int, db: Session = Depends(get_db)):
    db_franchise = db.query(Franchise).filter(Franchise.id == franchise_id).first()
    if not db_franchise:
        raise HTTPException(status_code=404, detail="Franquia não encontrada")
    db.delete(db_franchise)
    db.commit()
