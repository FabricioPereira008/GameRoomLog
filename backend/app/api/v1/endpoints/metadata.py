from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.metadata import (
    MetadataDetailsRequest, MetadataProposal, MetadataSearchRequest, MetadataSearchResponse,
)
from backend.app.services.metadata_service import (
    MetadataNotFoundError, MetadataSourceError, fetch_details, load_known_names, search_candidates,
)

router = APIRouter()


def _require_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Título do jogo não pode ser vazio.")
    return title


@router.post("/search", response_model=MetadataSearchResponse)
async def search_metadata(payload: MetadataSearchRequest):
    title = _require_title(payload.title)
    try:
        return await search_candidates(title, payload.igdb_client_id, payload.igdb_client_secret)
    except MetadataNotFoundError:
        raise HTTPException(status_code=404, detail=f"Nenhum jogo encontrado para '{title}'.")
    except MetadataSourceError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/details", response_model=MetadataProposal)
async def metadata_details(payload: MetadataDetailsRequest, db: Session = Depends(get_db)):
    title = _require_title(payload.title)
    known = load_known_names(db)
    try:
        return await fetch_details(payload.source, payload.source_id, title, known,
                                   payload.igdb_client_id, payload.igdb_client_secret)
    except MetadataNotFoundError:
        raise HTTPException(status_code=404, detail="Jogo não encontrado na fonte de dados.")
    except MetadataSourceError as e:
        raise HTTPException(status_code=502, detail=str(e))
