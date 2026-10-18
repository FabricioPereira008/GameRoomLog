"""Status de jogo (valores da API) e quais listas de jogos cada status alimenta."""
JOGANDO = "Jogando"
PROXIMO = "Próximo"
FILA = "Fila"
DISPONIVEL = "Disponível"
ZERADO = "Zerado"
PLATINADO = "Platinado"
LISTA_DE_DESEJOS = "Lista de Desejos"

# Chave da lista -> status que pertencem a ela (um jogo pode estar em mais de uma, ex.: Platinado)
LIST_STATUSES = {
    "queue": frozenset({FILA}),
    "disponiveis": frozenset({DISPONIVEL}),
    "zerados": frozenset({ZERADO, PLATINADO}),
    "platinados": frozenset({PLATINADO}),
    "wishlist": frozenset({LISTA_DE_DESEJOS}),
}


def in_list(list_key: str, status) -> bool:
    return status in LIST_STATUSES[list_key]


def filter_games(list_key: str, games: list) -> list:
    return [g for g in games if in_list(list_key, g.get("status"))]

# Ordem usada nos filtros de status (ex.: tabela da biblioteca)
ALL_STATUSES = [JOGANDO, FILA, PROXIMO, ZERADO, PLATINADO, DISPONIVEL, LISTA_DE_DESEJOS]


def is_completed(status) -> bool:
    return status in (ZERADO, PLATINADO)


def display_hours(game: dict) -> float:
    """Horas mostradas nos cards: jogadas para zerados/platinados; estimativa do HLTB para os demais."""
    key = "played_hours" if is_completed(game.get("status")) else "hltb_hours"
    return float(game.get(key) or 0.0)
