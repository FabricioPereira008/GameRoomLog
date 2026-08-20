from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.franchise import Franchise
from backend.app.schemas.franchise import FranchiseCreate, FranchiseUpdate, FranchiseResponse

router = APIRouter()

@router.get("/", response_model=List[FranchiseResponse])
def list_franchises(db: Session = Depends(get_db)):
    return db.query(Franchise).order_by(Franchise.name.asc()).all()

@router.post("/", response_model=FranchiseResponse, status_code=status.HTTP_201_CREATED)
def create_franchise(franchise_in: FranchiseCreate, db: Session = Depends(get_db)):
    existing = db.query(Franchise).filter(Franchise.name.ilike(franchise_in.name)).first()
    if existing:
        return existing
    db_franchise = Franchise(**franchise_in.model_dump())
    db.add(db_franchise)
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
