from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.developer import DeveloperCreate, DeveloperUpdate, DeveloperResponse
from backend.app.services.category_service import developer_service

from backend.app.schemas.category_detail import CategoryScope

router = APIRouter()

@router.get("/", response_model=List[DeveloperResponse])
def list_developers(scope: CategoryScope = "completed", db: Session = Depends(get_db)):
    return developer_service.list_with_counts(db, DeveloperResponse, scope)

@router.post("/", response_model=DeveloperResponse, status_code=status.HTTP_201_CREATED)
def create_developer(payload: DeveloperCreate, db: Session = Depends(get_db)):
    return developer_service.create(db, **payload.model_dump())

@router.put("/{dev_id}", response_model=DeveloperResponse)
def update_developer(dev_id: int, payload: DeveloperUpdate, db: Session = Depends(get_db)):
    return developer_service.update(db, dev_id, **payload.model_dump())

@router.delete("/{dev_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_developer(dev_id: int, db: Session = Depends(get_db)):
    developer_service.delete(db, dev_id)
