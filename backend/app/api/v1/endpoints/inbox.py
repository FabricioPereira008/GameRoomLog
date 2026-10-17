from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.inbox import (
    CatalogResponse, InboxImportResponse, InboxPackage, InboxPendingResponse, InboxProposalRequest, InboxResolveRequest,
    MatchCandidate,
    InboxResolveResponse,
)
from backend.app.services.inbox_service import (
    DEFAULT_THRESHOLD, InboxEventNotFoundError, UnsupportedVersionError, inbox_service,
)

router = APIRouter()


@router.post("/import", response_model=InboxImportResponse)
def import_inbox(payload: InboxPackage, db: Session = Depends(get_db)):
    """Recebe um pacote gameroom-inbox (arquivo hoje; o próprio app via rede no futuro)."""
    try:
        return inbox_service.import_package(db, payload)
    except UnsupportedVersionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/pending", response_model=InboxPendingResponse)
def list_pending(threshold: int = Query(DEFAULT_THRESHOLD, ge=50, le=100), db: Session = Depends(get_db)):
    return inbox_service.pending(db, threshold)


@router.post("/proposal", response_model=MatchCandidate)
def proposal_for_game(payload: InboxProposalRequest, threshold: int = Query(DEFAULT_THRESHOLD, ge=50, le=100),
                      db: Session = Depends(get_db)):
    try:
        return inbox_service.proposal_for(db, payload.event_ids, payload.game_id, threshold)
    except InboxEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/resolve", response_model=InboxResolveResponse)
def resolve_events(payload: InboxResolveRequest, db: Session = Depends(get_db)):
    try:
        resolved = inbox_service.resolve(db, payload.event_ids, payload.action, payload.game_id)
    except InboxEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return InboxResolveResponse(resolved=resolved)


@router.get("/catalog", response_model=CatalogResponse)
def export_catalog(db: Session = Depends(get_db)):
    """Snapshot gameroom-catalog para o app sugerir títulos e plataformas."""
    return inbox_service.catalog(db)
