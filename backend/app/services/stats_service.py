from collections import Counter
from datetime import date
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from backend.app.models.game import Game, GameStatus, PlayType
from backend.app.models.yearbook import YearbookPick
from backend.app.schemas.stats import CountItem, YearbookSummary, StatusCounts, OverallStats
from backend.app.schemas.game import GameResponse

COMPLETED = [GameStatus.ZERADO, GameStatus.PLATINADO]


class InvalidTop3Error(Exception):
    pass


class StatsService:
    @staticmethod
    def year_games(db: Session, year: int) -> List[Game]:
        """Jogos finalizados no ano (pela data de zeramento; sem data, pelo ano de conclusão)."""
        return db.query(Game).filter(
            or_(
                func.strftime("%Y", Game.finish_date) == str(year),
                (Game.finish_date.is_(None) & (Game.completion_year == year))
            ),
            Game.status.in_(COMPLETED)
        ).order_by(Game.finish_date.desc().nullslast()).all()

    @staticmethod
    def get_yearbook(db: Session, year: int) -> YearbookSummary:
        games = StatsService.year_games(db, year)
        hours = {g.id: g.played_hours or g.hltb_hours or 0.0 for g in games}  # horas jogadas (ou HLTB)

        total_hltb = sum(g.hltb_hours or 0.0 for g in games)
        scores = [g.score for g in games if g.score is not None]
        difficulties = [g.difficulty for g in games if g.difficulty is not None]

        monthly = [0] * 12
        for g in games:
            if g.finish_date:
                monthly[g.finish_date.month - 1] += 1

        genres: Dict[str, CountItem] = {}
        platforms: Dict[str, CountItem] = {}
        for g in games:
            for genre in g.genres:
                item = genres.setdefault(genre.name, CountItem(name=genre.name, count=0, color=genre.color))
                item.count += 1
                item.hours += hours[g.id]
            pname = g.platform.name if g.platform else "Sem plataforma"
            item = platforms.setdefault(pname, CountItem(name=pname, count=0))
            item.count += 1
            item.hours += hours[g.id]

        def ranked(items, by_hours=False):
            key = (lambda i: (-i.hours, -i.count, i.name.casefold())) if by_hours else (lambda i: (-i.count, -i.hours, i.name.casefold()))
            out = sorted(items, key=key)
            for i in out:
                i.hours = round(i.hours, 1)
            return out

        def top_names(values) -> List[CountItem]:
            counts = Counter(v for v in values if v)
            return [CountItem(name=n, count=c) for n, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].casefold()))[:5]]

        def best_by(key):
            pool = [g for g in games if key(g) is not None]
            return GameResponse.model_validate(max(pool, key=lambda g: (key(g), hours[g.id]))) if pool else None

        previous = len(StatsService.year_games(db, year - 1))
        top3, custom = StatsService.podium(db, year, games, hours)

        return YearbookSummary(
            year=year,
            total_games_finished=len(games),
            total_platinums=sum(1 for g in games if g.status == GameStatus.PLATINADO),
            total_hours_played=round(sum(hours.values()), 1),
            total_hltb_hours=round(total_hltb, 1),
            average_score=round(sum(scores) / len(scores), 1) if scores else None,
            games=[GameResponse.model_validate(g) for g in games],
            previous_year_finished=previous,
            monthly_finished=monthly,
            genres=ranked(genres.values()),
            platforms=ranked(platforms.values(), by_hours=True),
            developers=top_names(g.developer for g in games),
            franchises=top_names(g.franchise.name if g.franchise else None for g in games),
            average_difficulty=round(sum(difficulties) / len(difficulties), 1) if difficulties else None,
            average_hours=round(sum(hours.values()) / len(games), 1) if games else None,
            replays=sum(1 for g in games if g.play_type == PlayType.REJOGADA),
            longest_game=best_by(lambda g: hours[g.id] or None),
            best_game=best_by(lambda g: g.score),
            hardest_game=best_by(lambda g: g.difficulty),
            top3=[GameResponse.model_validate(g) for g in top3],
            top3_custom=custom,
        )

    @staticmethod
    def podium(db: Session, year: int, games: List[Game], hours: Dict[int, float]):
        """(jogos do pódio, escolhido pelo usuário?). Escolhas que deixaram de valer para o ano são ignoradas."""
        by_id = {g.id: g for g in games}
        picks = db.query(YearbookPick).filter(YearbookPick.year == year).order_by(YearbookPick.position).all()
        chosen = [by_id[p.game_id] for p in picks if p.game_id in by_id]
        if chosen:
            return chosen, True
        suggested = sorted(games, key=lambda g: (g.score is None, -(g.score or 0), -hours[g.id], g.title.casefold()))
        return suggested[:3], False

    @staticmethod
    def set_top3(db: Session, year: int, game_ids: List[int]) -> YearbookSummary:
        """Grava o pódio do ano (lista vazia volta para a sugestão). Só jogos finalizados no ano."""
        if len(set(game_ids)) != len(game_ids):
            raise InvalidTop3Error("Um jogo não pode ocupar duas posições")
        valid = {g.id for g in StatsService.year_games(db, year)}
        invalid = [gid for gid in game_ids if gid not in valid]
        if invalid:
            raise InvalidTop3Error(f"Jogos não finalizados em {year}: {invalid}")
        db.query(YearbookPick).filter(YearbookPick.year == year).delete()
        for position, gid in enumerate(game_ids, 1):
            db.add(YearbookPick(year=year, position=position, game_id=gid))
        db.commit()
        return StatsService.get_yearbook(db, year)

    @staticmethod
    def get_overall_stats(db: Session) -> OverallStats:
        # Contagem por status
        counts_query = db.query(Game.status, func.count(Game.id)).group_by(Game.status).all()
        counts_dict = {status: count for status, count in counts_query}

        status_counts = StatusCounts(
            jogando=counts_dict.get(GameStatus.JOGANDO, 0),
            proximos=counts_dict.get(GameStatus.PROXIMO, 0),
            fila=counts_dict.get(GameStatus.FILA, 0),
            zerados=counts_dict.get(GameStatus.ZERADO, 0),
            platinados=counts_dict.get(GameStatus.PLATINADO, 0),
            disponivel=counts_dict.get(GameStatus.DISPONIVEL, 0),
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
            available_years = [date.today().year]

        return OverallStats(
            status_counts=status_counts,
            total_hours=round(total_hours, 1),
            available_years=available_years
        )
