"""Identificadores, títulos e ícones das telas (única fonte para sidebar, cabeçalho e navegação)."""
from dataclasses import dataclass
from enum import IntEnum


class ViewId(IntEnum):
    GAME_ROOM = 0
    QUEUE = 1
    AVAILABLE = 2
    FINISHED = 3
    PLATINUM = 4
    YEARBOOK = 5
    GENRES = 6
    PLATFORMS = 7
    FRANCHISES = 8
    LIBRARY = 9
    WISHLIST = 10
    SETTINGS = 11
    CATEGORY_DETAIL = 12
    SYNC = 13
    PORTABLE = 14


@dataclass(frozen=True)
class ViewMeta:
    title: str       # título no cabeçalho
    nav_label: str   # rótulo na sidebar
    icon: str        # nome do SVG em resources/icons


VIEW_META = {
    ViewId.GAME_ROOM: ViewMeta("Game Room", "Game Room", "gamepad-2"),
    ViewId.QUEUE: ViewMeta("Fila de espera", "Fila de espera", "list-ordered"),
    ViewId.AVAILABLE: ViewMeta("Jogos disponíveis", "Disponíveis", "library"),
    ViewId.FINISHED: ViewMeta("Jogos zerados", "Zerados", "circle-check"),
    ViewId.PLATINUM: ViewMeta("Jogos platinados", "Platinados", "trophy"),
    ViewId.WISHLIST: ViewMeta("Lista de desejos", "Lista de desejos", "gift"),
    ViewId.LIBRARY: ViewMeta("Biblioteca de jogos", "Biblioteca (tabela)", "table-2"),
    ViewId.YEARBOOK: ViewMeta("Anuário gamer", "Anuário", "calendar-days"),
    ViewId.GENRES: ViewMeta("Gêneros", "Gêneros", "tags"),
    ViewId.PLATFORMS: ViewMeta("Plataformas", "Plataformas", "monitor"),
    ViewId.FRANCHISES: ViewMeta("Séries / franquias", "Séries / franquias", "layers"),
    ViewId.SETTINGS: ViewMeta("Configurações", "Configurações", "settings"),
    ViewId.SYNC: ViewMeta("Sincronizar bibliotecas", "Sincronizar lojas", "refresh-cw"),
    ViewId.PORTABLE: ViewMeta("App do portátil", "App do portátil", "smartphone"),
    ViewId.CATEGORY_DETAIL: ViewMeta("Detalhes da categoria", "Detalhes", "tags"),
}

# Grupos exibidos na sidebar, na ordem
NAV_SECTIONS = [
    ("Biblioteca", [ViewId.GAME_ROOM, ViewId.QUEUE, ViewId.AVAILABLE, ViewId.FINISHED,
                    ViewId.PLATINUM, ViewId.WISHLIST, ViewId.LIBRARY]),
    ("Explorar", [ViewId.YEARBOOK, ViewId.GENRES, ViewId.PLATFORMS, ViewId.FRANCHISES]),
    ("Importar", [ViewId.SYNC, ViewId.PORTABLE]),
]
