from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.platform import PlatformCreate, PlatformUpdate, PlatformResponse
from backend.app.schemas.category_detail import CategoryDetailResponse, CategoryScope
from backend.app.services.category_service import platform_service

router = APIRouter()

@router.get("/", response_model=List[PlatformResponse])
def list_platforms(scope: CategoryScope = "completed", db: Session = Depends(get_db)):
    return platform_service.list_with_counts(db, PlatformResponse, scope)

@router.get("/{platform_id}/details", response_model=CategoryDetailResponse)
def get_platform_details(platform_id: int, scope: CategoryScope = "completed", db: Session = Depends(get_db)):
    return platform_service.details(db, platform_id, scope)

@router.post("/", response_model=PlatformResponse, status_code=status.HTTP_201_CREATED)
def create_platform(payload: PlatformCreate, db: Session = Depends(get_db)):
    return platform_service.create(db, **payload.model_dump())

@router.put("/{platform_id}", response_model=PlatformResponse)
def update_platform(platform_id: int, payload: PlatformUpdate, db: Session = Depends(get_db)):
    return platform_service.update(db, platform_id, **payload.model_dump())

@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_platform(platform_id: int, db: Session = Depends(get_db)):
    platform_service.delete(db, platform_id)
