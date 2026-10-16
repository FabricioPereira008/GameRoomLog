from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.franchise import FranchiseCreate, FranchiseUpdate, FranchiseResponse
from backend.app.schemas.category_detail import CategoryDetailResponse
from backend.app.services.category_service import franchise_service

router = APIRouter()

@router.get("/", response_model=List[FranchiseResponse])
def list_franchises(db: Session = Depends(get_db)):
    return franchise_service.list_with_counts(db, FranchiseResponse)

@router.get("/{franchise_id}/details", response_model=CategoryDetailResponse)
def get_franchise_details(franchise_id: int, db: Session = Depends(get_db)):
    return franchise_service.details(db, franchise_id)

@router.post("/", response_model=FranchiseResponse, status_code=status.HTTP_201_CREATED)
def create_franchise(payload: FranchiseCreate, db: Session = Depends(get_db)):
    return franchise_service.create(db, **payload.model_dump())

@router.put("/{franchise_id}", response_model=FranchiseResponse)
def update_franchise(franchise_id: int, payload: FranchiseUpdate, db: Session = Depends(get_db)):
    return franchise_service.update(db, franchise_id, **payload.model_dump())

@router.delete("/{franchise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_franchise(franchise_id: int, db: Session = Depends(get_db)):
    franchise_service.delete(db, franchise_id)
