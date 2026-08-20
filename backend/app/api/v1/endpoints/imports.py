from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.services.notion_importer import NotionImporterService

router = APIRouter()

class NotionImportRequest(BaseModel):
    folder_path: str
    auto_fetch_covers: bool = True

class NotionImportResponse(BaseModel):
    total_found: int
    imported: int
    updated: int
    covers_queue_count: int
    errors: List[str]

@router.post("/notion", response_model=NotionImportResponse, status_code=status.HTTP_200_OK)
def import_from_notion(
    payload: NotionImportRequest,
    db: Session = Depends(get_db)
):
    try:
        result = NotionImporterService.import_notion_folder(
            db=db,
            folder_path=payload.folder_path,
            auto_fetch_covers=payload.auto_fetch_covers
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro durante a importação do Notion: {str(e)}")
