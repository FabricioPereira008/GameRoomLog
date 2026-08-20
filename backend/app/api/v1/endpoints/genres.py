from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.models.genre import Genre
from backend.app.schemas.genre import GenreCreate, GenreUpdate, GenreResponse

router = APIRouter()

@router.get("/", response_model=List[GenreResponse])
def list_genres(db: Session = Depends(get_db)):
    return db.query(Genre).order_by(Genre.name.asc()).all()

@router.post("/", response_model=GenreResponse, status_code=status.HTTP_201_CREATED)
def create_genre(genre_in: GenreCreate, db: Session = Depends(get_db)):
    existing = db.query(Genre).filter(Genre.name.ilike(genre_in.name)).first()
    if existing:
        return existing
    db_genre = Genre(**genre_in.model_dump())
    db.add(db_genre)
    db.commit()
    db.refresh(db_genre)
    return db_genre

@router.delete("/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_genre(genre_id: int, db: Session = Depends(get_db)):
    db_genre = db.query(Genre).filter(Genre.id == genre_id).first()
    if not db_genre:
        raise HTTPException(status_code=404, detail="Gênero não encontrado")
    db.delete(db_genre)
    db.commit()
