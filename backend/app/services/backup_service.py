"""Backups do banco SQLite: automático ao iniciar (1 por dia), manual e restauração.

As cópias usam a API de backup do SQLite (consistente mesmo com o banco aberto) e ficam em
`<pasta do banco>/backups`, mantendo as MAX_BACKUPS mais recentes.
"""
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

MAX_BACKUPS = 10
NAME_RE = re.compile(r"^gameroom-(\d{8})-(\d{6})(?:-([a-z-]+))?\.db$")
REASON_LABELS = {"auto": "Automático", "manual": "Manual", "antes-da-restauracao": "Antes de restaurar"}


class BackupNotFoundError(Exception):
    pass


class InvalidBackupError(Exception):
    pass


def database_path(engine: Engine) -> Optional[Path]:
    """Arquivo do banco (None para bancos em memória)."""
    db = engine.url.database
    if engine.url.get_backend_name() != "sqlite" or not db or db == ":memory:":
        return None
    return Path(db).resolve()


def backup_dir(engine: Engine) -> Optional[Path]:
    path = database_path(engine)
    return path.parent / "backups" if path else None


def _info(path: Path) -> dict:
    match = NAME_RE.match(path.name)
    created = datetime.strptime(match.group(1) + match.group(2), "%Y%m%d%H%M%S")
    reason = match.group(3) or "auto"
    games = None
    try:  # quantos jogos tinha (ajuda a escolher qual restaurar)
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            games = conn.execute("select count(*) from games").fetchone()[0]
    except sqlite3.Error:
        pass
    return {
        "name": path.name,
        "created_at": created,
        "reason": reason,
        "reason_label": REASON_LABELS.get(reason, reason),
        "size_bytes": path.stat().st_size,
        "games_count": games,
    }


def list_backups(engine: Engine) -> List[dict]:
    folder = backup_dir(engine)
    if not folder or not folder.is_dir():
        return []
    files = [p for p in folder.iterdir() if p.is_file() and NAME_RE.match(p.name)]
    return sorted((_info(p) for p in files), key=lambda b: (b["created_at"], b["name"]), reverse=True)


def _prune(folder: Path) -> None:
    files = sorted((p for p in folder.iterdir() if p.is_file() and NAME_RE.match(p.name)), key=lambda p: p.name)
    for old in files[:-MAX_BACKUPS]:
        old.unlink(missing_ok=True)


def create_backup(engine: Engine, reason: str = "manual", prune: bool = True) -> dict:
    folder = backup_dir(engine)
    if folder is None:
        raise InvalidBackupError("Banco em memória não tem backup")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = folder / (f"gameroom-{stamp}.db" if reason == "auto" else f"gameroom-{stamp}-{reason}.db")
    counter = 1
    while target.exists():  # dois backups no mesmo segundo
        target = folder / f"gameroom-{stamp}-{reason}-{'x' * counter}.db"
        counter += 1
    raw = engine.raw_connection()
    try:
        with sqlite3.connect(target) as dst:
            raw.driver_connection.backup(dst)
    finally:
        raw.close()
    if prune:
        _prune(folder)
    logger.info("Backup do banco criado: %s", target.name)
    return _info(target)


def auto_backup(engine: Engine) -> Optional[dict]:
    """Backup do dia, antes das migrações. Ignora banco novo (sem jogos) e se já houver um backup hoje."""
    folder = backup_dir(engine)
    if folder is None or "games" not in inspect(engine).get_table_names():
        return None
    today = datetime.now().strftime("%Y%m%d")
    if folder.is_dir() and any(NAME_RE.match(p.name) and p.name[9:17] == today for p in folder.iterdir()):
        return None
    try:
        return create_backup(engine, reason="auto")
    except Exception:  # backup nunca impede o app de abrir
        logger.exception("Falha no backup automático do banco")
        return None


def restore_backup(engine: Engine, name: str, migrate) -> dict:
    """Substitui o conteúdo do banco pelo backup `name` (o estado atual é salvo antes) e aplica migrações."""
    if not NAME_RE.match(name or ""):
        raise InvalidBackupError("Nome de backup inválido")
    folder = backup_dir(engine)
    source = (folder / name) if folder else None
    if source is None or not source.is_file():
        raise BackupNotFoundError(name)
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src:
            src.execute("select count(*) from games").fetchone()
    except sqlite3.Error as exc:
        raise InvalidBackupError(f"O arquivo não é um banco do GameRoom válido: {exc}")

    # Sem limpar ainda: com MAX_BACKUPS cheio, o arquivo restaurado poderia ser o apagado
    safety = create_backup(engine, reason="antes-da-restauracao", prune=False)
    raw = engine.raw_connection()
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src:
            src.backup(raw.driver_connection)
    finally:
        raw.close()
    engine.dispose()  # conexões antigas do pool não devem guardar estado do banco anterior
    migrate(engine)  # backups antigos podem estar numa versão anterior do schema
    _prune(folder)
    logger.info("Banco restaurado a partir de %s (estado anterior salvo em %s)", name, safety["name"])
    return {"restored": name, "safety_backup": safety["name"]}
