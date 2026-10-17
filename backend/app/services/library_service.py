"""Sincronização de bibliotecas de lojas: scan, deduplicação, importação e lista de ignorados."""
import logging
import re
import unicodedata
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from backend.app.models.game import Game, GameFormat, GameStatus
from backend.app.models.platform import Platform
from backend.app.models.store_link import GameStoreLink, IgnoredStoreGame
from backend.app.schemas.library import Candidate, ImportItem, LibraryEntryBase, ScanResponse, StoreError
from backend.app.services.library.base import PROVIDERS, LibraryEntry, LibraryProviderError

logger = logging.getLogger(__name__)

DEFAULT_PLATFORM_NAME = "PC"
MAX_TITLE_LEN = 200

_NON_GAME_RE = re.compile(
    r"steamworks common redistributables|\bproton\b|steam linux runtime|dedicated server"
    r"|\bsoundtrack\b|\bost\b|\bsdk\b|\bbenchmark\b",
    re.IGNORECASE,
)


class UnknownStoreError(Exception):
    pass


def normalize_title(title: str) -> str:
    """Minúsculas, sem acentos, sem ™/®/©, sem pontuação, espaços colapsados."""
    text = re.sub(r"[™®©]", "", title)  # antes do NFKD, que decomporia ™ em "TM"
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"['’`´]", "", text)  # "Dragon's" e "Dragons" devem coincidir
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def looks_like_non_game(title: str) -> bool:
    return bool(_NON_GAME_RE.search(title))


class LibraryService:
    @staticmethod
    def scan(db: Session, stores: Optional[Sequence[str]] = None, include_all: bool = False) -> ScanResponse:
        """Busca nas lojas e devolve os jogos que ainda não estão no GameRoom.

        Efeito colateral: jogos cadastrados à mão com título idêntico (correspondência única)
        são vinculados à loja automaticamente.
        """
        selected = list(stores) if stores else list(PROVIDERS)
        unknown = [s for s in selected if s not in PROVIDERS]
        if unknown:
            raise UnknownStoreError(f"Loja desconhecida: {', '.join(unknown)}")

        errors: List[StoreError] = []
        entries: List[LibraryEntry] = []
        for store in selected:
            try:
                entries.extend(PROVIDERS[store]().fetch())
            except LibraryProviderError as exc:
                errors.append(StoreError(store=store, message=str(exc)))
            except Exception as exc:  # não vaza detalhes: podem conter segredos
                logger.error("Falha inesperada no provedor %s: %s", store, type(exc).__name__)
                errors.append(StoreError(store=store, message="Falha inesperada ao ler a biblioteca."))

        linked: Set[Tuple[str, str]] = {
            (s, e) for s, e in db.query(GameStoreLink.store, GameStoreLink.external_id)
        }
        ignored: Set[Tuple[str, str]] = {
            (s, e) for s, e in db.query(IgnoredStoreGame.store, IgnoredStoreGame.external_id)
        }
        by_title: Dict[str, List[int]] = defaultdict(list)
        for game_id, title in db.query(Game.id, Game.title):
            by_title[normalize_title(title)].append(game_id)

        candidates: List[Candidate] = []
        auto_linked = 0
        seen: Set[Tuple[str, str]] = set()
        for entry in entries:
            key = (entry.store, entry.external_id)
            if key in linked or key in ignored or key in seen:
                continue
            seen.add(key)
            if not include_all and (not entry.is_game or looks_like_non_game(entry.title)):
                continue
            matches = by_title.get(normalize_title(entry.title), []) if normalize_title(entry.title) else []
            if len(matches) == 1:
                db.add(GameStoreLink(game_id=matches[0], store=entry.store, external_id=entry.external_id))
                auto_linked += 1
                continue
            candidates.append(Candidate(
                store=entry.store,
                external_id=entry.external_id,
                title=entry.title[:MAX_TITLE_LEN],
                played_hours=entry.played_hours,
                ambiguous=len(matches) > 1,
            ))
        db.commit()
        candidates.sort(key=lambda c: c.title.lower())
        return ScanResponse(candidates=candidates, auto_linked=auto_linked, errors=errors)

    @staticmethod
    def _default_platform(db: Session) -> Platform:
        platform = db.query(Platform).filter(Platform.name.ilike(DEFAULT_PLATFORM_NAME)).first()
        if not platform:
            platform = Platform(name=DEFAULT_PLATFORM_NAME, icon_name="pc")
            db.add(platform)
            db.flush()
        return platform

    @staticmethod
    def import_items(db: Session, items: Sequence[ImportItem]) -> Tuple[List[Game], int]:
        """Cria um jogo (Digital/Disponível/PC) por item e o vincula à loja. Idempotente por (loja, id)."""
        platform = LibraryService._default_platform(db)
        existing: Set[Tuple[str, str]] = {
            (s, e) for s, e in db.query(GameStoreLink.store, GameStoreLink.external_id)
        }
        created: List[Game] = []
        skipped = 0
        for item in items:
            key = (item.store, item.external_id)
            if key in existing:
                skipped += 1
                continue
            existing.add(key)
            game = Game(
                title=item.title.strip(),
                platform_id=platform.id,
                status=GameStatus.DISPONIVEL,
                format=GameFormat.DIGITAL,
                played_hours=item.played_hours or 0.0,
            )
            game.store_links.append(GameStoreLink(store=item.store, external_id=item.external_id))
            # Um item importado deixa de ser "ignorado", caso estivesse
            db.query(IgnoredStoreGame).filter_by(store=item.store, external_id=item.external_id).delete()
            db.add(game)
            created.append(game)
        db.commit()
        for game in created:
            db.refresh(game)
        return created, skipped

    @staticmethod
    def ignore(db: Session, items: Sequence[LibraryEntryBase]) -> int:
        count = 0
        for item in items:
            exists = db.query(IgnoredStoreGame).filter_by(store=item.store, external_id=item.external_id).first()
            if exists:
                continue
            db.add(IgnoredStoreGame(store=item.store, external_id=item.external_id, title=item.title.strip()))
            count += 1
        db.commit()
        return count

    @staticmethod
    def list_ignored(db: Session) -> List[IgnoredStoreGame]:
        return db.query(IgnoredStoreGame).order_by(IgnoredStoreGame.title).all()

    @staticmethod
    def unignore(db: Session, ignored_id: int) -> bool:
        row = db.query(IgnoredStoreGame).filter(IgnoredStoreGame.id == ignored_id).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True


library_service = LibraryService()
