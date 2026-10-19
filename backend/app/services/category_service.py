"""Regras de negócio compartilhadas pelas categorias (gêneros, plataformas, franquias, desenvolvedoras)."""
from typing import Any, Callable, List, Optional, Type

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.app.models.developer import Developer
from backend.app.models.franchise import Franchise
from backend.app.models.game import Game, GameStatus, game_genres
from backend.app.models.genre import Genre
from backend.app.models.platform import Platform
from backend.app.schemas.category_detail import CategoryDetailResponse
from backend.app.schemas.game import GameResponse

COMPLETED_STATUSES = [GameStatus.ZERADO, GameStatus.PLATINADO]
SCOPE_COMPLETED, SCOPE_ALL = "completed", "all"  # páginas de categoria: só concluídos ou todos os jogos
MAX_COVER_SAMPLES = 4


class CategoryNotFoundError(Exception):
    pass


class CategoryConflictError(Exception):
    pass


class CategoryService:
    """CRUD + contagens para uma categoria de jogos.

    `game_filter(category_id)` retorna a condição SQLAlchemy que liga um Game à categoria.
    """

    def __init__(
        self,
        model: Type[Any],
        label: str,
        not_found: str,
        category_type: str,
        game_filter: Optional[Callable[[int], Any]] = None,
        updatable_fields: tuple = ("name",),
        game_fk: Optional[Any] = None,
    ):
        self.model = model
        self.label = label
        self.not_found = not_found
        self.category_type = category_type
        self.game_filter = game_filter
        self.updatable_fields = updatable_fields
        self.game_fk = game_fk

    # --- consultas ---
    def get(self, db: Session, category_id: int):
        obj = db.query(self.model).filter(self.model.id == category_id).first()
        if not obj:
            raise CategoryNotFoundError(self.not_found)
        return obj

    def completed_counts(self, db: Session, completed_only: bool = True) -> dict:
        """Mapa id -> quantidade de jogos (só concluídos ou todos), em uma única consulta agrupada."""
        raise NotImplementedError

    def completed_rows(self, db: Session, completed_only: bool = True) -> list:
        """Linhas (category_id, cover_image, hours, concluído?) com os concluídos primeiro, melhor nota/mais horas."""
        raise NotImplementedError

    def completed_summary(self, db: Session, completed_only: bool = True) -> dict:
        """Mapa id -> {"hours": horas dos concluídos, "covers": até MAX_COVER_SAMPLES capas} (uma consulta)."""
        summary: dict = {}
        for category_id, cover, hours, done in self.completed_rows(db, completed_only):
            if category_id is None:
                continue
            entry = summary.setdefault(category_id, {"hours": 0.0, "covers": []})
            if done:
                entry["hours"] += hours or 0.0
            if cover and len(entry["covers"]) < MAX_COVER_SAMPLES and cover not in entry["covers"]:
                entry["covers"].append(cover)
        return summary

    def list_with_counts(self, db: Session, response_cls: Type[Any], scope: str = SCOPE_COMPLETED) -> List[Any]:
        """`scope="completed"` conta/mostra só os concluídos; `"all"` considera todos os jogos."""
        completed_only = scope != SCOPE_ALL
        completed = self.completed_counts(db)
        counts = completed if completed_only else self.completed_counts(db, completed_only=False)
        summary = self.completed_summary(db, completed_only)
        results = []
        for obj in db.query(self.model).order_by(self.model.name.asc()).all():
            resp = response_cls.model_validate(obj)
            resp.games_count = counts.get(obj.id, 0)
            resp.completed_count = completed.get(obj.id, 0)
            info = summary.get(obj.id)
            if info:
                resp.total_hours = round(info["hours"], 1)
                resp.cover_samples = info["covers"]
            results.append(resp)
        return results

    def details(self, db: Session, category_id: int, scope: str = SCOPE_COMPLETED, **extra) -> CategoryDetailResponse:
        obj = self.get(db, category_id)
        query = db.query(Game).options(joinedload(Game.developer_rel)).filter(self.game_filter(category_id))
        if scope != SCOPE_ALL:
            query = query.filter(Game.status.in_(COMPLETED_STATUSES))
        games = query.order_by(Game.finish_date.desc().nullslast(), Game.title.asc()).all()
        done = [g for g in games if g.status in COMPLETED_STATUSES]
        total_hours = sum(g.played_hours or g.hltb_hours or 0.0 for g in done)
        return CategoryDetailResponse(
            id=obj.id,
            name=obj.name,
            category_type=self.category_type,
            total_games=len(games),
            completed_games=len(done),
            total_hours_played=round(total_hours, 1),
            games=[GameResponse.model_validate(g) for g in games],
            **{k: getattr(obj, k) for k in extra.get("attrs", ())},
        )

    # --- escrita ---
    def _find_by_name(self, db: Session, name: str):
        return db.query(self.model).filter(self.model.name.ilike(name)).first()

    def create(self, db: Session, **fields):
        name = fields["name"].strip()
        existing = self._find_by_name(db, name)
        if existing:
            return existing
        fields["name"] = name
        obj = self.model(**{k: v for k, v in fields.items() if v is not None})
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, category_id: int, **fields):
        obj = self.get(db, category_id)
        new_name = fields.get("name")
        if new_name is not None:
            duplicate = self._find_by_name(db, new_name.strip())
            if duplicate and duplicate.id != obj.id:
                raise CategoryConflictError(f"Já existe {self.label} com o nome '{new_name.strip()}'")
        for key in self.updatable_fields:
            value = fields.get(key)
            if value is not None:
                setattr(obj, key, value.strip())
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise CategoryConflictError(f"Já existe {self.label} com esse nome")
        db.refresh(obj)
        return obj

    def delete(self, db: Session, category_id: int) -> None:
        obj = self.get(db, category_id)
        if self.game_fk is not None:
            # Desvincula os jogos antes de remover (FKs sem ON DELETE em bancos já criados)
            db.query(Game).filter(self.game_fk == category_id).update(
                {self.game_fk: None}, synchronize_session=False
            )
        db.delete(obj)
        db.commit()


def _is_completed():
    return case((Game.status.in_(COMPLETED_STATUSES), 1), else_=0)


def _ranked_completed(db: Session, *columns, completed_only: bool = True):
    """Jogos com `columns` + capa + horas + concluído?, concluídos primeiro e depois por nota e horas."""
    query = db.query(*columns, Game.cover_image, func.coalesce(Game.played_hours, Game.hltb_hours, 0.0), _is_completed())
    if completed_only:
        query = query.filter(Game.status.in_(COMPLETED_STATUSES))
    return query.order_by(
        _is_completed().desc(), Game.score.desc().nullslast(), Game.played_hours.desc().nullslast(), Game.id.asc()
    )


def _group_counts(db: Session, key_column, *conditions, completed_only: bool = True) -> dict:
    query = db.query(key_column, func.count(Game.id)).filter(*conditions)
    if completed_only:
        query = query.filter(Game.status.in_(COMPLETED_STATUSES))
    return {k: c for k, c in query.group_by(key_column).all() if k is not None}


class GenreService(CategoryService):
    def __init__(self):
        super().__init__(
            Genre, "um gênero", "Gênero não encontrado", "genre",
            game_filter=lambda gid: Game.genres.any(Genre.id == gid),
            updatable_fields=("name", "color"),
        )

    def completed_counts(self, db: Session, completed_only: bool = True) -> dict:
        query = db.query(game_genres.c.genre_id, func.count(game_genres.c.game_id)).join(Game, Game.id == game_genres.c.game_id)
        if completed_only:
            query = query.filter(Game.status.in_(COMPLETED_STATUSES))
        return {k: c for k, c in query.group_by(game_genres.c.genre_id).all()}

    def completed_rows(self, db: Session, completed_only: bool = True) -> list:
        return (
            _ranked_completed(db, game_genres.c.genre_id, completed_only=completed_only)
            .join(game_genres, game_genres.c.game_id == Game.id)
            .all()
        )

    def create(self, db: Session, **fields):
        fields["color"] = fields.get("color") or "#4f46e5"
        return super().create(db, **fields)

    def details(self, db: Session, category_id: int, scope: str = SCOPE_COMPLETED, **extra):
        return super().details(db, category_id, scope, attrs=("color",))


class PlatformService(CategoryService):
    def __init__(self):
        super().__init__(
            Platform, "uma plataforma", "Plataforma não encontrada", "platform",
            game_filter=lambda pid: Game.platform_id == pid,
            updatable_fields=("name", "icon_name"),
            game_fk=Game.platform_id,
        )

    def completed_counts(self, db: Session, completed_only: bool = True) -> dict:
        return _group_counts(db, Game.platform_id, completed_only=completed_only)

    def completed_rows(self, db: Session, completed_only: bool = True) -> list:
        return _ranked_completed(db, Game.platform_id, completed_only=completed_only).all()

    def details(self, db: Session, category_id: int, scope: str = SCOPE_COMPLETED, **extra):
        return super().details(db, category_id, scope, attrs=("icon_name",))


class FranchiseService(CategoryService):
    def __init__(self):
        super().__init__(
            Franchise, "uma franquia", "Franquia não encontrada", "franchise",
            game_filter=lambda fid: Game.franchise_id == fid,
            game_fk=Game.franchise_id,
        )

    def completed_counts(self, db: Session, completed_only: bool = True) -> dict:
        return _group_counts(db, Game.franchise_id, completed_only=completed_only)

    def completed_rows(self, db: Session, completed_only: bool = True) -> list:
        return _ranked_completed(db, Game.franchise_id, completed_only=completed_only).all()


class DeveloperService(CategoryService):
    def __init__(self):
        super().__init__(
            Developer, "uma desenvolvedora", "Desenvolvedora não encontrada", "developer",
            game_filter=lambda did: Game.developer_id == did,
            game_fk=Game.developer_id,
        )

    def completed_counts(self, db: Session, completed_only: bool = True) -> dict:
        return _group_counts(db, Game.developer_id, completed_only=completed_only)

    def completed_rows(self, db: Session, completed_only: bool = True) -> list:
        return _ranked_completed(db, Game.developer_id, completed_only=completed_only).all()


genre_service = GenreService()
platform_service = PlatformService()
franchise_service = FranchiseService()
developer_service = DeveloperService()
