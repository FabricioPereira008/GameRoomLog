from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from backend.app.models.game import Game, GameStatus
from backend.app.schemas.stats import YearbookSummary, StatusCounts, OverallStats
from backend.app.schemas.game import GameResponse

class StatsService:
    @staticmethod
    def get_yearbook(db: Session, year: int) -> YearbookSummary:
        # Jogos finalizados no ano especificado (baseado estritamente no ano em que foi zerado)
        games = db.query(Game).filter(
            or_(
                func.strftime("%Y", Game.finish_date) == str(year),
                (Game.finish_date.is_(None) & (Game.completion_year == year))
            ),
            Game.status.in_([GameStatus.ZERADO, GameStatus.PLATINADO])
        ).order_by(Game.finish_date.desc().nullslast()).all()

        total_games = len(games)
        total_platinums = sum(1 for g in games if g.status == GameStatus.PLATINADO)
        
        # Soma de horas jogadas (ou HLTB se played_hours for 0)
        total_hours = sum(g.played_hours or g.hltb_hours or 0.0 for g in games)
        total_hltb = sum(g.hltb_hours or 0.0 for g in games)

        scored_games = [g.score for g in games if g.score is not None]
        avg_score = round(sum(scored_games) / len(scored_games), 1) if scored_games else None

        return YearbookSummary(
            year=year,
            total_games_finished=total_games,
            total_platinums=total_platinums,
            total_hours_played=round(total_hours, 1),
            total_hltb_hours=round(total_hltb, 1),
            average_score=avg_score,
            games=[GameResponse.model_validate(g) for g in games]
        )

    @staticmethod
    def get_overall_stats(db: Session) -> OverallStats:
        # Contagem por status
        counts_query = db.query(Game.status, func.count(Game.id)).group_by(Game.status).all()
        counts_dict = {status: count for status, count in counts_query}

        status_counts = StatusCounts(
            jogando=counts_dict.get(GameStatus.JOGANDO, 0),
            proximos=counts_dict.get(GameStatus.PROXIMO, 0),
            fila=counts_dict.get(GameStatus.FILA, 0),
            pausados=counts_dict.get(GameStatus.PAUSADO, 0),
            zerados=counts_dict.get(GameStatus.ZERADO, 0),
            platinados=counts_dict.get(GameStatus.PLATINADO, 0),
            disponivel=counts_dict.get(GameStatus.DISPONIVEL, 0),
            desisti=counts_dict.get(GameStatus.DESISTI, 0),
            wishlist=counts_dict.get(GameStatus.WISHLIST, 0),
            total=sum(counts_dict.values())
        )

        # Total de horas jogadas de todos os jogos zerados/platinados
        hours_res = db.query(func.sum(Game.played_hours)).filter(
            Game.status.in_([GameStatus.ZERADO, GameStatus.PLATINADO])
        ).scalar()
        total_hours = float(hours_res) if hours_res else 0.0

        # Anos disponíveis baseados estritamente na finalização do jogo (finish_date / completion_year)
        years_query = db.query(func.strftime("%Y", Game.finish_date)).filter(
            Game.finish_date.isnot(None),
            Game.status.in_([GameStatus.ZERADO, GameStatus.PLATINADO])
        ).distinct().all()
        available_years = [int(y[0]) for y in years_query if y[0]]

        # Complementar com completion_year para casos sem finish_date explícito
        cy_query = db.query(Game.completion_year).filter(
            Game.completion_year.isnot(None),
            Game.status.in_([GameStatus.ZERADO, GameStatus.PLATINADO])
        ).distinct().all()
        for cy in cy_query:
            if cy[0] and cy[0] not in available_years:
                available_years.append(cy[0])

        available_years.sort(reverse=True)
        if not available_years:
            available_years = [2026]

        return OverallStats(
            status_counts=status_counts,
            total_hours=round(total_hours, 1),
            available_years=available_years
        )
