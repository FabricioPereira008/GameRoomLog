from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.models.franchise import Franchise
from backend.app.models.game import Game
from backend.app.schemas.franchise import FranchiseCreate, FranchiseUpdate, FranchiseResponse

router = APIRouter()

@router.get("/", response_model=List[FranchiseResponse])
def list_franchises(db: Session = Depends(get_db)):
    franchises = db.query(Franchise).order_by(Franchise.name.asc()).all()
    results = []
    for f in franchises:
        count = db.query(func.count(Game.id)).filter(Game.franchise_id == f.id).scalar() or 0
        resp = FranchiseResponse.model_validate(f)
        resp.games_count = count
        results.append(resp)
    return results

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
    count = db.query(func.count(Game.id)).filter(Game.franchise_id == db_franchise.id).scalar() or 0
    resp = FranchiseResponse.model_validate(db_franchise)
    resp.games_count = count
    return resp

@router.delete("/{franchise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_franchise(franchise_id: int, db: Session = Depends(get_db)):
    db_franchise = db.query(Franchise).filter(Franchise.id == franchise_id).first()
    if not db_franchise:
        raise HTTPException(status_code=404, detail="Franquia não encontrada")
    db.delete(db_franchise)
    db.commit()
