from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.library import (
    IgnoredResponse, IgnoreRequest, ImportRequest, ImportResponse, LibrarySettingsResponse,
    LibrarySettingsUpdate, LinkRequest, LinkResponse, ScanRequest, ScanResponse,
)
from backend.app.services.library.settings_store import LibrarySettings, load_settings, save_settings
from backend.app.services.library_service import (
    GameNotFoundError, StoreLinkConflictError, UnknownStoreError, library_service,
)

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


@router.post("/link", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
def link_game(payload: LinkRequest, db: Session = Depends(get_db)):
    try:
        return library_service.link_game(db, payload.game_id, payload.store, payload.external_id)
    except GameNotFoundError:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    except StoreLinkConflictError:
        raise HTTPException(status_code=409, detail="Este item da loja já está vinculado a outro jogo")


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


def _settings_response(cfg: LibrarySettings) -> LibrarySettingsResponse:
    return LibrarySettingsResponse(steam_api_key_set=bool(cfg.steam_api_key), steam_id=cfg.steam_id,
                                   heroic_path=cfg.heroic_path)


@router.get("/settings", response_model=LibrarySettingsResponse)
def get_library_settings():
    return _settings_response(load_settings())


@router.put("/settings", response_model=LibrarySettingsResponse)
def update_library_settings(payload: LibrarySettingsUpdate):
    cfg = load_settings()
    if payload.steam_api_key is not None:
        cfg.steam_api_key = payload.steam_api_key.strip()
    if payload.steam_id is not None:
        cfg.steam_id = payload.steam_id.strip()
    if payload.heroic_path is not None:
        cfg.heroic_path = payload.heroic_path.strip()
    save_settings(cfg)
    return _settings_response(cfg)
