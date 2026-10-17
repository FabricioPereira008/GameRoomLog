from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.library import (
    IgnoredResponse, IgnoreRequest, ImportRequest, ImportResponse, ScanRequest, ScanResponse,
)
from backend.app.services.library_service import UnknownStoreError, library_service

router = APIRouter()


@router.post("/scan", response_model=ScanResponse)
def scan_libraries(payload: ScanRequest, db: Session = Depends(get_db)):
    try:
        return library_service.scan(db, payload.stores, payload.include_all)
    except UnknownStoreError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
def import_games(payload: ImportRequest, db: Session = Depends(get_db)):
    games, skipped = library_service.import_items(db, payload.items)
    return ImportResponse(imported=games, skipped=skipped)


@router.post("/ignored", status_code=status.HTTP_201_CREATED)
def ignore_games(payload: IgnoreRequest, db: Session = Depends(get_db)):
    return {"ignored": library_service.ignore(db, payload.items)}


@router.get("/ignored", response_model=List[IgnoredResponse])
def list_ignored(db: Session = Depends(get_db)):
    return library_service.list_ignored(db)


@router.delete("/ignored/{ignored_id}", status_code=status.HTTP_204_NO_CONTENT)
def unignore_game(ignored_id: int, db: Session = Depends(get_db)):
    if not library_service.unignore(db, ignored_id):
        raise HTTPException(status_code=404, detail="Item ignorado não encontrado")
