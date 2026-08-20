from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.models.developer import Developer
from backend.app.models.game import Game, GameStatus
from backend.app.schemas.developer import DeveloperCreate, DeveloperUpdate, DeveloperResponse

router = APIRouter()

@router.get("/", response_model=List[DeveloperResponse])
def list_developers(db: Session = Depends(get_db)):
    devs = db.query(Developer).order_by(Developer.name.asc()).all()
    results = []
    for d in devs:
        count = db.query(func.count(Game.id)).filter(
            ((Game.developer_id == d.id) | (Game.developer.ilike(d.name))),
            Game.status.in_([GameStatus.ZERADO, GameStatus.PLATINADO])
        ).scalar() or 0
        resp = DeveloperResponse.model_validate(d)
        resp.games_count = count
        results.append(resp)
    return results

@router.post("/", response_model=DeveloperResponse, status_code=status.HTTP_201_CREATED)
def create_developer(dev_in: DeveloperCreate, db: Session = Depends(get_db)):
    existing = db.query(Developer).filter(Developer.name.ilike(dev_in.name.strip())).first()
    if existing:
        return existing
    db_dev = Developer(name=dev_in.name.strip())
    db.add(db_dev)
    db.commit()
    db.refresh(db_dev)
    return db_dev

@router.put("/{dev_id}", response_model=DeveloperResponse)
def update_developer(dev_id: int, dev_in: DeveloperUpdate, db: Session = Depends(get_db)):
    db_dev = db.query(Developer).filter(Developer.id == dev_id).first()
    if not db_dev:
        raise HTTPException(status_code=404, detail="Desenvolvedora não encontrada")
    if dev_in.name is not None:
        db_dev.name = dev_in.name.strip()
    db.commit()
    db.refresh(db_dev)
    return db_dev

@router.delete("/{dev_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_developer(dev_id: int, db: Session = Depends(get_db)):
    db_dev = db.query(Developer).filter(Developer.id == dev_id).first()
    if not db_dev:
        raise HTTPException(status_code=404, detail="Desenvolvedora não encontrada")
    db.delete(db_dev)
    db.commit()
