from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc, update, func
from backend.app.models.game import Game, GameStatus, PlayType, game_genres
from backend.app.models.genre import Genre
from backend.app.models.developer import Developer
from backend.app.schemas.game import GameCreate, GameUpdate
from backend.app.services.cover_service import discard_cover_if_unused

MAX_REPLAY_DEPTH = 50  # proteção contra ciclos em dados antigos/corrompidos


class ReplayLinkError(Exception):
    """Vínculo de rejogada inválido (vira 422 na API)."""


class GameService:
    @staticmethod
    def attach_replay_counts(db: Session, games: List[Game]) -> List[Game]:
        """Preenche `replays_count` (rejogadas vinculadas a cada registro) com uma única consulta."""
        if not games:
            return games
        query = db.query(Game.replay_of_id, func.count(Game.id)).filter(Game.replay_of_id.isnot(None))
        if len(games) <= 500:
            query = query.filter(Game.replay_of_id.in_([g.id for g in games]))
        counts = dict(query.group_by(Game.replay_of_id).all())
        for game in games:
            game.replays_count = counts.get(game.id, 0)
        return games

    @staticmethod
    def replay_root(db: Session, game: Game) -> Game:
        """Registro original (1ª jogada) do grupo de jogadas de `game`."""
        current = game
        for _ in range(MAX_REPLAY_DEPTH):
            if current.replay_of_id is None:
                return current
            parent = db.get(Game, current.replay_of_id)
            if parent is None:
                return current
            current = parent
        return current

    @staticmethod
    def _link_replay(db: Session, data: dict, game_id: Optional[int] = None) -> None:
        """Valida `replay_of_id` e o aponta para o registro original; rejogada vinculada é sempre Rejogada."""
        target_id = data.get("replay_of_id")
        if target_id is None:
            if data.get("play_type") == PlayType.PRIMEIRA_JOGADA:
                data["replay_of_id"] = None  # deixou de ser rejogada: desfaz o vínculo
            return
        if target_id == game_id:
            raise ReplayLinkError("Um jogo não pode ser rejogada de si mesmo")
        target = db.get(Game, target_id)
        if target is None:
            raise ReplayLinkError("Jogo original não encontrado")
        root = GameService.replay_root(db, target)
        if game_id is not None and root.id == game_id:
            raise ReplayLinkError("Este jogo já é o original desse grupo de jogadas")
        data["replay_of_id"] = root.id
        data["play_type"] = PlayType.REJOGADA

    @staticmethod
    def get_briefs(db: Session) -> List[dict]:
        rows = db.query(Game).options(joinedload(Game.platform)).order_by(asc(Game.title), asc(Game.id)).all()
        return [{
            "id": g.id, "title": g.title, "status": g.status, "platform": g.platform.name if g.platform else None,
            "play_type": g.play_type, "play_count": g.play_count, "replay_of_id": g.replay_of_id,
            "finish_date": g.finish_date, "completion_year": g.completion_year, "score": g.score,
        } for g in rows]

    @staticmethod
    def get_games(
        db: Session,
        status: Optional[GameStatus] = None,
        platform_id: Optional[int] = None,
        genre_id: Optional[int] = None,
        franchise_id: Optional[int] = None,
        completion_year: Optional[int] = None,
        is_favorite: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = "title_asc"
    ) -> List[Game]:
        query = db.query(Game).options(
            joinedload(Game.platform),
            joinedload(Game.franchise),
            joinedload(Game.developer_rel),
            joinedload(Game.genres)
        )

        if status:
            query = query.filter(Game.status == status)
        if platform_id:
            query = query.filter(Game.platform_id == platform_id)
        if franchise_id:
            query = query.filter(Game.franchise_id == franchise_id)
        if completion_year:
            query = query.filter(Game.completion_year == completion_year)
        if is_favorite is not None:
            query = query.filter(Game.is_favorite == is_favorite)
        if genre_id:
            query = query.filter(Game.genres.any(Genre.id == genre_id))
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Game.title.ilike(search_term),
                    Game.developer.ilike(search_term)
                )
            )

        if sort_by == "title_asc":
            query = query.order_by(asc(Game.title))
        elif sort_by == "title_desc":
            query = query.order_by(desc(Game.title))
        elif sort_by == "score_desc":
            query = query.order_by(desc(Game.score).nullslast())
        elif sort_by == "hltb_asc":
            query = query.order_by(asc(Game.hltb_hours).nullslast())
        elif sort_by == "finish_date_desc":
            query = query.order_by(desc(Game.finish_date).nullslast())
        elif sort_by == "recent":
            query = query.order_by(desc(Game.updated_at))
        else:
            query = query.order_by(asc(Game.title))

        return GameService.attach_replay_counts(db, query.all())

    @staticmethod
    def get_game_by_id(db: Session, game_id: int) -> Optional[Game]:
        game = db.query(Game).options(
            joinedload(Game.platform),
            joinedload(Game.franchise),
            joinedload(Game.developer_rel),
            joinedload(Game.genres)
        ).filter(Game.id == game_id).first()
        if game is not None:
            GameService.attach_replay_counts(db, [game])
        return game

    @staticmethod
    def _sync_developer(db: Session, data: dict) -> None:
        """Mantém `developer` (nome) e `developer_id` coerentes; developer_id tem precedência.

        Só age sobre as chaves presentes em `data` (serve para create e update parcial).
        """
        if data.get("developer_id"):
            dev = db.query(Developer).filter(Developer.id == data["developer_id"]).first()
            if dev:
                data["developer"] = dev.name
            return
        if "developer" not in data and "developer_id" not in data:
            return
        dev_name = (data.get("developer") or "").strip()
        if dev_name:
            dev = db.query(Developer).filter(Developer.name.ilike(dev_name)).first()
            if not dev:
                dev = Developer(name=dev_name)
                db.add(dev)
                db.flush()
            data["developer_id"] = dev.id
            data["developer"] = dev.name
        else:
            data["developer"] = None
            data["developer_id"] = None

    @staticmethod
    def _set_genres(db: Session, db_game: Game, genre_ids: List[int]) -> None:
        """Grava os gêneros na ordem recebida (1º = principal), ignorando ids repetidos ou inexistentes."""
        ordered = list(dict.fromkeys(genre_ids))
        found = {g.id: g for g in db.query(Genre).filter(Genre.id.in_(ordered)).all()}
        ordered = [gid for gid in ordered if gid in found]
        db_game.genres = [found[gid] for gid in ordered]
        db.flush()
        for position, genre_id in enumerate(ordered):
            db.execute(
                update(game_genres)
                .where(game_genres.c.game_id == db_game.id, game_genres.c.genre_id == genre_id)
                .values(position=position)
            )
        db.expire(db_game, ["genres"])  # recarrega já na ordem de position

    @staticmethod
    def create_game(db: Session, game_in: GameCreate) -> Game:
        data = game_in.model_dump(exclude={"genre_ids"})

        GameService._sync_developer(db, data)
        GameService._link_replay(db, data)

        # Se preencheu finish_date ou platinum_date mas não completion_year, calcula o ano
        if not data.get("completion_year"):
            if data.get("finish_date"):
                data["completion_year"] = data["finish_date"].year
            elif data.get("platinum_date"):
                data["completion_year"] = data["platinum_date"].year
            elif data.get("status") in [GameStatus.ZERADO, GameStatus.PLATINADO]:
                data["completion_year"] = date.today().year

        db_game = Game(**data)

        db.add(db_game)
        if game_in.genre_ids:
            GameService._set_genres(db, db_game, game_in.genre_ids)
        db.commit()
        db.refresh(db_game)
        return GameService.attach_replay_counts(db, [db_game])[0]

    @staticmethod
    def update_game(db: Session, game_id: int, game_in: GameUpdate) -> Optional[Game]:
        db_game = GameService.get_game_by_id(db, game_id)
        if not db_game:
            return None

        update_data = game_in.model_dump(exclude_unset=True)
        genre_ids = update_data.pop("genre_ids", None)
        old_cover = db_game.cover_image

        GameService._sync_developer(db, update_data)
        GameService._link_replay(db, update_data, game_id)
        if update_data.get("replay_of_id") is not None:
            # Era o original de outras jogadas: elas passam para o novo original
            db.query(Game).filter(Game.replay_of_id == game_id).update(
                {Game.replay_of_id: update_data["replay_of_id"]}, synchronize_session=False)

        for key, value in update_data.items():
            setattr(db_game, key, value)

        # Atualiza completion_year automaticamente
        if db_game.finish_date:
            db_game.completion_year = db_game.finish_date.year
        elif db_game.platinum_date:
            db_game.completion_year = db_game.platinum_date.year
        elif db_game.status in [GameStatus.ZERADO, GameStatus.PLATINADO] and not db_game.completion_year:
            db_game.completion_year = date.today().year

        if genre_ids is not None:
            GameService._set_genres(db, db_game, genre_ids)

        db.commit()
        if old_cover and old_cover != db_game.cover_image:
            discard_cover_if_unused(db, old_cover)  # capa trocada: o arquivo antigo não serve mais
        db.refresh(db_game)
        return GameService.attach_replay_counts(db, [db_game])[0]


    @staticmethod
    def delete_game(db: Session, game_id: int) -> bool:
        db_game = GameService.get_game_by_id(db, game_id)
        if not db_game:
            return False
        cover = db_game.cover_image
        replays = db.query(Game).filter(Game.replay_of_id == game_id).order_by(asc(Game.id)).all()
        if replays:  # o original saiu: a jogada mais antiga que sobrou vira o original do grupo
            new_root, others = replays[0], replays[1:]
            new_root.replay_of_id = None
            for replay in others:
                replay.replay_of_id = new_root.id
            db.flush()
        db.delete(db_game)
        db.commit()
        discard_cover_if_unused(db, cover)
        return True
