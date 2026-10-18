"""Campos que faltam no cadastro de um jogo (filtro "Incompletos" e aviso nos cards)."""
from typing import List

from frontend_desktop.views import game_status as gs


def missing_fields(game: dict) -> List[str]:
    """Nomes legíveis dos campos vazios; jogos zerados/platinados também precisam dos dados da jogada."""
    missing = []
    if not (game.get("developer") or "").strip():
        missing.append("desenvolvedora")
    if not game.get("genres"):
        missing.append("gênero")
    if not game.get("platform"):
        missing.append("plataforma")
    if not game.get("cover_image"):
        missing.append("capa")
    if not game.get("hltb_hours"):
        missing.append("duração (HLTB)")
    status = game.get("status")
    if status in (gs.ZERADO, gs.PLATINADO):
        if not game.get("played_hours"):
            missing.append("horas jogadas")
        if game.get("score") is None:
            missing.append("nota")
        if not game.get("finish_date"):
            missing.append("data de zeramento")
    if status == gs.PLATINADO and not game.get("platinum_date"):
        missing.append("data da platina")
    return missing


def is_incomplete(game: dict) -> bool:
    return bool(missing_fields(game))
