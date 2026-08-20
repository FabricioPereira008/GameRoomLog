from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc
from backend.app.models.game import Game, GameStatus, game_genres
from backend.app.models.genre import Genre
from backend.app.schemas.game import GameCreate, GameUpdate

class GameService:
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

        return query.all()

    @staticmethod
    def get_game_by_id(db: Session, game_id: int) -> Optional[Game]:
        return db.query(Game).options(
            joinedload(Game.platform),
            joinedload(Game.franchise),
            joinedload(Game.genres)
        ).filter(Game.id == game_id).first()

    @staticmethod
    def create_game(db: Session, game_in: GameCreate) -> Game:
        data = game_in.model_dump(exclude={"genre_ids"})
        
        # Se preencheu finish_date mas não completion_year, calcula o ano
        if data.get("finish_date") and not data.get("completion_year"):
            data["completion_year"] = data["finish_date"].year

        db_game = Game(**data)

        if game_in.genre_ids:
            genres = db.query(Genre).filter(Genre.id.in_(game_in.genre_ids)).all()
            db_game.genres = genres

        db.add(db_game)
        db.commit()
        db.refresh(db_game)
        return db_game

    @staticmethod
    def update_game(db: Session, game_id: int, game_in: GameUpdate) -> Optional[Game]:
        db_game = GameService.get_game_by_id(db, game_id)
        if not db_game:
            return None

        update_data = game_in.model_dump(exclude_unset=True)
        genre_ids = update_data.pop("genre_ids", None)

        for key, value in update_data.items():
            setattr(db_game, key, value)

        # Atualizar completion_year se finish_date foi alterada
        if "finish_date" in update_data and update_data["finish_date"]:
            if "completion_year" not in update_data or not update_data["completion_year"]:
                db_game.completion_year = update_data["finish_date"].year

        if genre_ids is not None:
            genres = db.query(Genre).filter(Genre.id.in_(genre_ids)).all()
            db_game.genres = genres

        db.commit()
        db.refresh(db_game)
        return db_game

    @staticmethod
    def delete_game(db: Session, game_id: int) -> bool:
        db_game = GameService.get_game_by_id(db, game_id)
        if not db_game:
            return False
        db.delete(db_game)
        db.commit()
        return True
