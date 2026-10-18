from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.engine import Engine

from backend.app.core.database import engine as default_engine
from backend.app.core.migrations import run_migrations
from backend.app.schemas.backup import BackupInfo, BackupList, RestoreResponse
from backend.app.services import backup_service
from backend.app.services.backup_service import BackupNotFoundError, InvalidBackupError

router = APIRouter()


def get_engine() -> Engine:
    """Banco alvo dos backups (substituível nos testes)."""
    return default_engine


@router.get("/", response_model=BackupList)
def list_backups(engine: Engine = Depends(get_engine)):
    folder = backup_service.backup_dir(engine)
    return BackupList(folder=str(folder) if folder else None, max_backups=backup_service.MAX_BACKUPS,
                      backups=backup_service.list_backups(engine))


@router.post("/", response_model=BackupInfo, status_code=status.HTTP_201_CREATED)
def create_backup(engine: Engine = Depends(get_engine)):
    try:
        return backup_service.create_backup(engine, reason="manual")
    except InvalidBackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{name}/restore", response_model=RestoreResponse)
def restore_backup(name: str, engine: Engine = Depends(get_engine)):
    try:
        return backup_service.restore_backup(engine, name, run_migrations)
    except BackupNotFoundError:
        raise HTTPException(status_code=404, detail="Backup não encontrado")
    except InvalidBackupError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
