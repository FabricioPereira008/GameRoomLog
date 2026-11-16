"""Regras dos rankings de favoritos usadas na GUI (espelham backend/app/services/ranking_service.py)."""
from typing import Optional

FILTER_TYPES = (("genre", "Gênero"), ("franchise", "Série / franquia"), ("platform", "Plataforma"))
FILTER_FIELD = {"genre": "genre_id", "franchise": "franchise_id", "platform": "platform_id"}
FILTER_NAMES = dict(FILTER_TYPES)


def game_matches(ranking: dict, game: dict) -> bool:
    """O jogo pode entrar no ranking? Gênero vale em qualquer posição (principal ou secundário)."""
    if ranking.get("genre_id") is not None:
        return any(g.get("id") == ranking["genre_id"] for g in game.get("genres") or [])
    if ranking.get("franchise_id") is not None:
        return (game.get("franchise_id") or (game.get("franchise") or {}).get("id")) == ranking["franchise_id"]
    if ranking.get("platform_id") is not None:
        return (game.get("platform_id") or (game.get("platform") or {}).get("id")) == ranking["platform_id"]
    return True


def entry_ids(ranking: dict) -> list:
    return [g["id"] for g in ranking.get("entries") or []]


def is_full(ranking: dict) -> bool:
    return len(ranking.get("entries") or []) >= ranking.get("max_size", 0)


def filter_text(ranking: dict) -> Optional[str]:
    """Ex.: "Gênero: Soulslike" (None sem filtro)."""
    kind = ranking.get("filter_type")
    if not kind:
        return None
    return f"{FILTER_NAMES.get(kind, kind)}: {ranking.get('filter_label') or '—'}"


def add_block_reason(ranking: dict, game: dict) -> Optional[str]:
    """Por que o jogo não pode ser adicionado ao ranking (None = pode)."""
    if game.get("id") in entry_ids(ranking):
        return "já está no ranking"
    if is_full(ranking):
        return "ranking completo"
    if not game_matches(ranking, game):
        return "fora do filtro"
    return None
