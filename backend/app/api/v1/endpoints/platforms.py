from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.core.database import get_db
from backend.app.models.platform import Platform
from backend.app.models.game import Game
from backend.app.schemas.platform import PlatformCreate, PlatformUpdate, PlatformResponse
from backend.app.schemas.category_detail import CategoryDetailResponse
from backend.app.schemas.game import GameResponse

router = APIRouter()

@router.get("/", response_model=List[PlatformResponse])
def list_platforms(db: Session = Depends(get_db)):
    platforms = db.query(Platform).order_by(Platform.name.asc()).all()
    results = []
    for p in platforms:
        count = db.query(func.count(Game.id)).filter(Game.platform_id == p.id).scalar() or 0
        resp = PlatformResponse.model_validate(p)
        resp.games_count = count
        results.append(resp)
    return results

@router.get("/{platform_id}/details", response_model=CategoryDetailResponse)
def get_platform_details(platform_id: int, db: Session = Depends(get_db)):
    platform = db.query(Platform).filter(Platform.id == platform_id).first()
    if not platform:
        raise HTTPException(status_code=404, detail="Plataforma não encontrada")

    games = db.query(Game).filter(Game.platform_id == platform_id).order_by(Game.title.asc()).all()
    total_hours = sum(g.played_hours or g.hltb_hours or 0.0 for g in games)

    return CategoryDetailResponse(
        id=platform.id,
        name=platform.name,
        category_type="platform",
        icon_name=platform.icon_name,
        total_games=len(games),
        total_hours_played=round(total_hours, 1),
        games=[GameResponse.model_validate(g) for g in games]
    )

@router.post("/", response_model=PlatformResponse, status_code=status.HTTP_201_CREATED)
def create_platform(platform_in: PlatformCreate, db: Session = Depends(get_db)):
    existing = db.query(Platform).filter(Platform.name.ilike(platform_in.name.strip())).first()
    if existing:
        return existing
    db_platform = Platform(name=platform_in.name.strip(), icon_name=platform_in.icon_name)
    db.add(db_platform)
    db.commit()
    db.refresh(db_platform)
    return db_platform

@router.put("/{platform_id}", response_model=PlatformResponse)
def update_platform(platform_id: int, platform_in: PlatformUpdate, db: Session = Depends(get_db)):
    db_platform = db.query(Platform).filter(Platform.id == platform_id).first()
    if not db_platform:
        raise HTTPException(status_code=404, detail="Plataforma não encontrada")
    if platform_in.name is not None:
        db_platform.name = platform_in.name.strip()
    if platform_in.icon_name is not None:
        db_platform.icon_name = platform_in.icon_name
    db.commit()
    db.refresh(db_platform)
    count = db.query(func.count(Game.id)).filter(Game.platform_id == db_platform.id).scalar() or 0
    resp = PlatformResponse.model_validate(db_platform)
    resp.games_count = count
    return resp

@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
    db_platform = db.query(Platform).filter(Platform.id == platform_id).first()
    if not db_platform:
        raise HTTPException(status_code=404, detail="Plataforma não encontrada")
    db.delete(db_platform)
    db.commit()
