from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.platform import Platform
from backend.app.schemas.platform import PlatformCreate, PlatformUpdate, PlatformResponse

router = APIRouter()

@router.get("/", response_model=List[PlatformResponse])
def list_platforms(db: Session = Depends(get_db)):
    return db.query(Platform).order_by(Platform.name.asc()).all()

@router.post("/", response_model=PlatformResponse, status_code=status.HTTP_201_CREATED)
def create_platform(platform_in: PlatformCreate, db: Session = Depends(get_db)):
    existing = db.query(Platform).filter(Platform.name.ilike(platform_in.name)).first()
    if existing:
        return existing
    db_platform = Platform(**platform_in.model_dump())
    db.add(db_platform)
    db.commit()
    db.refresh(db_platform)
    return db_platform

@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
    db_platform = db.query(Platform).filter(Platform.id == platform_id).first()
    if not db_platform:
        raise HTTPException(status_code=404, detail="Plataforma não encontrada")
    db.delete(db_platform)
    db.commit()
