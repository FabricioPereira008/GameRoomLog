from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.genre import GenreCreate, GenreUpdate, GenreResponse
from backend.app.schemas.category_detail import CategoryDetailResponse
from backend.app.services.category_service import genre_service

router = APIRouter()

@router.get("/", response_model=List[GenreResponse])
def list_genres(db: Session = Depends(get_db)):
    return genre_service.list_with_counts(db, GenreResponse)

@router.get("/{genre_id}/details", response_model=CategoryDetailResponse)
def get_genre_details(genre_id: int, db: Session = Depends(get_db)):
    return genre_service.details(db, genre_id)

@router.post("/", response_model=GenreResponse, status_code=status.HTTP_201_CREATED)
def create_genre(payload: GenreCreate, db: Session = Depends(get_db)):
    return genre_service.create(db, **payload.model_dump())

@router.put("/{genre_id}", response_model=GenreResponse)
def update_genre(genre_id: int, payload: GenreUpdate, db: Session = Depends(get_db)):
    return genre_service.update(db, genre_id, **payload.model_dump())

@router.delete("/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_genre(genre_id: int, db: Session = Depends(get_db)):
    genre_service.delete(db, genre_id)
