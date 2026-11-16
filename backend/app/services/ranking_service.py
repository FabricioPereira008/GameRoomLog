"""Rankings pessoais de jogos favoritos (ex.: "Top 10 de todos os tempos", "Top Soulslike")."""
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.franchise import Franchise
from backend.app.models.game import Game
from backend.app.models.genre import Genre
from backend.app.models.platform import Platform
from backend.app.models.ranking import Ranking, RankingEntry
from backend.app.schemas.game import GameResponse
from backend.app.schemas.ranking import (
    FILTER_FIELDS, GameRankingPosition, RankingCreate, RankingResponse, RankingUpdate,
)
from backend.app.services.game_service import GameService

FILTER_MODELS = {"genre_id": (Genre, "genre"), "franchise_id": (Franchise, "franchise"),
                 "platform_id": (Platform, "platform")}


class RankingNotFoundError(Exception):
    pass


class RankingConflictError(Exception):
    pass


class InvalidRankingError(Exception):
    pass


def game_matches(ranking: Ranking, game: Game) -> bool:
    """O jogo pode entrar no ranking? Gênero vale em qualquer posição (principal ou secundário)."""
    if ranking.genre_id is not None:
        return any(g.id == ranking.genre_id for g in game.genres)
    if ranking.franchise_id is not None:
        return game.franchise_id == ranking.franchise_id
    if ranking.platform_id is not None:
        return game.platform_id == ranking.platform_id
    return True


class RankingService:
    @staticmethod
    def _get(db: Session, ranking_id: int) -> Ranking:
        ranking = db.get(Ranking, ranking_id)
        if ranking is None:
            raise RankingNotFoundError(f"Ranking {ranking_id} não encontrado")
        return ranking

    @staticmethod
    def to_response(db: Session, ranking: Ranking) -> RankingResponse:
        games = GameService.attach_replay_counts(db, [e.game for e in ranking.entries])
        filter_type = filter_label = None
        for field, (_, attr) in FILTER_MODELS.items():
            if getattr(ranking, field) is not None:
                filter_type = attr
                filter_label = getattr(getattr(ranking, attr), "name", None)
        return RankingResponse(
            id=ranking.id, name=ranking.name, max_size=ranking.max_size, position=ranking.position,
            genre_id=ranking.genre_id, franchise_id=ranking.franchise_id, platform_id=ranking.platform_id,
            filter_type=filter_type, filter_label=filter_label,
            entries=[GameResponse.model_validate(g) for g in games],
            out_of_filter_ids=[g.id for g in games if not game_matches(ranking, g)],
        )

    @staticmethod
    def _check_filter_exists(db: Session, data: dict) -> None:
        for field, (model, _) in FILTER_MODELS.items():
            value = data.get(field)
            if value is not None and db.get(model, value) is None:
                raise InvalidRankingError(f"Filtro inexistente: {field}={value}")

    @staticmethod
    def _check_name(db: Session, name: str, ranking_id: Optional[int] = None) -> None:
        query = db.query(Ranking).filter(func.lower(Ranking.name) == name.strip().lower())
        if ranking_id is not None:
            query = query.filter(Ranking.id != ranking_id)
        if query.first() is not None:
            raise RankingConflictError(f"Já existe um ranking chamado '{name.strip()}'")

    @staticmethod
    def list_rankings(db: Session) -> List[RankingResponse]:
        rankings = db.query(Ranking).order_by(Ranking.position, Ranking.id).all()
        return [RankingService.to_response(db, r) for r in rankings]

    @staticmethod
    def get_ranking(db: Session, ranking_id: int) -> RankingResponse:
        return RankingService.to_response(db, RankingService._get(db, ranking_id))

    @staticmethod
    def create_ranking(db: Session, data: RankingCreate) -> RankingResponse:
        values = data.model_dump()
        values["name"] = values["name"].strip()
        RankingService._check_name(db, values["name"])
        RankingService._check_filter_exists(db, values)
        last = db.query(func.max(Ranking.position)).scalar()
        ranking = Ranking(**values, position=(last + 1) if last is not None else 0)
        db.add(ranking)
        db.commit()
        db.refresh(ranking)
        return RankingService.to_response(db, ranking)

    @staticmethod
    def update_ranking(db: Session, ranking_id: int, data: RankingUpdate) -> RankingResponse:
        ranking = RankingService._get(db, ranking_id)
        values = data.model_dump(exclude_unset=True)
        if values.get("name") is not None:
            values["name"] = values["name"].strip()
            RankingService._check_name(db, values["name"], ranking_id)
        elif "name" in values:
            values.pop("name")
        if values.get("max_size") is None:
            values.pop("max_size", None)
        RankingService._check_filter_exists(db, values)
        if any(f in values for f in FILTER_FIELDS):
            # trocar o filtro substitui o anterior (só um pode estar ativo)
            for field in FILTER_FIELDS:
                setattr(ranking, field, values.pop(field, None))
        for key, value in values.items():
            setattr(ranking, key, value)
        # tamanho menor corta as posições excedentes
        for entry in list(ranking.entries):
            if entry.position > ranking.max_size:
                db.delete(entry)
        db.commit()
        db.refresh(ranking)
        return RankingService.to_response(db, ranking)

    @staticmethod
    def delete_ranking(db: Session, ranking_id: int) -> None:
        db.delete(RankingService._get(db, ranking_id))
        db.commit()

    @staticmethod
    def reorder_rankings(db: Session, ranking_ids: List[int]) -> List[RankingResponse]:
        rankings = {r.id: r for r in db.query(Ranking).all()}
        if sorted(ranking_ids) != sorted(rankings):
            raise InvalidRankingError("A nova ordem precisa conter todos os rankings, uma vez cada")
        for position, rid in enumerate(ranking_ids):
            rankings[rid].position = position
        db.commit()
        return RankingService.list_rankings(db)

    @staticmethod
    def set_entries(db: Session, ranking_id: int, game_ids: List[int]) -> RankingResponse:
        """Grava as posições do ranking na ordem dada (1º primeiro). Lista vazia esvazia o ranking."""
        ranking = RankingService._get(db, ranking_id)
        if len(set(game_ids)) != len(game_ids):
            raise InvalidRankingError("Um jogo não pode ocupar duas posições")
        if len(game_ids) > ranking.max_size:
            raise InvalidRankingError(f"O ranking tem só {ranking.max_size} posições")
        games = {g.id: g for g in db.query(Game).filter(Game.id.in_(game_ids)).all()} if game_ids else {}
        missing = [gid for gid in game_ids if gid not in games]
        if missing:
            raise InvalidRankingError(f"Jogos inexistentes: {missing}")
        # quem já estava pode ficar mesmo fora do filtro; jogo novo precisa casar
        current = {e.game_id for e in ranking.entries}
        invalid = [gid for gid in game_ids if gid not in current and not game_matches(ranking, games[gid])]
        if invalid:
            raise InvalidRankingError(f"Jogos fora do filtro do ranking: {invalid}")
        db.query(RankingEntry).filter(RankingEntry.ranking_id == ranking_id).delete()
        db.flush()
        for position, gid in enumerate(game_ids, 1):
            db.add(RankingEntry(ranking_id=ranking_id, position=position, game_id=gid))
        db.commit()
        db.expire(ranking)
        return RankingService.to_response(db, ranking)

    @staticmethod
    def rankings_for_game(db: Session, game_id: int) -> List[GameRankingPosition]:
        rows = (db.query(Ranking.id, Ranking.name, RankingEntry.position)
                .join(RankingEntry, RankingEntry.ranking_id == Ranking.id)
                .filter(RankingEntry.game_id == game_id)
                .order_by(Ranking.position, Ranking.id).all())
        return [GameRankingPosition(ranking_id=rid, name=name, position=pos) for rid, name, pos in rows]

    @staticmethod
    def ranking_ids_with_game(db: Session, game_id: int) -> List[int]:
        return [rid for (rid,) in db.query(RankingEntry.ranking_id).filter(RankingEntry.game_id == game_id)]

    @staticmethod
    def compact(db: Session, ranking_ids: List[int]) -> None:
        """Depois de excluir um jogo (a entrada sai por cascade), renumera as posições para 1..n."""
        for rid in ranking_ids:
            ids = [gid for (gid,) in db.query(RankingEntry.game_id).filter(RankingEntry.ranking_id == rid)
                   .order_by(RankingEntry.position)]
            db.query(RankingEntry).filter(RankingEntry.ranking_id == rid).delete()
            db.flush()
            for position, gid in enumerate(ids, 1):
                db.add(RankingEntry(ranking_id=rid, position=position, game_id=gid))
        db.commit()
