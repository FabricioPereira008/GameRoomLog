"""Personalização das páginas de jogos: critérios de ordenação e campos do Filtro visíveis.

Cada página tem um conjunto fixo de critérios e campos possíveis (PAGES); o usuário escolhe quais
aparecem e a ordenação padrão (Configurações → Páginas). A escolha fica no QSettings deste
computador e vale na hora para as páginas abertas (`subscribe`).

A ordenação escolhida na própria página vale só enquanto o app está aberto: ao reabrir, cada
página volta à ordenação padrão configurada aqui.
"""
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from frontend_desktop import preferences
from frontend_desktop.text_search import fold
from frontend_desktop.views.game_status import display_hours


def _positive(value) -> Optional[float]:
    """Número > 0 ou None (0 horas/sem nota contam como "sem valor")."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _present(value):
    return value if value not in (None, "") else None


DIRECTION_LABELS = {  # kind -> (crescente, decrescente)
    "text": ("A→Z", "Z→A"),
    "date": ("Antigos primeiro", "Recentes primeiro"),
    "number": ("Menor→Maior", "Maior→Menor"),
}


@dataclass(frozen=True)
class SortCriterion:
    label: str
    key: Callable[[dict], object]  # None = sem valor (vai sempre para o fim)
    descending: bool               # direção inicial: maior/mais recente primeiro
    kind: str = "number"           # text | date | number (rótulos do botão de direção)

    def direction_label(self, descending: bool) -> str:
        return DIRECTION_LABELS[self.kind][1 if descending else 0]


SORT_CRITERIA: Dict[str, SortCriterion] = {
    "finish_date": SortCriterion("Data de zeramento", lambda g: _present(g.get("finish_date")), True, "date"),
    "platinum_date": SortCriterion("Data de platina", lambda g: _present(g.get("platinum_date")), True, "date"),
    "score": SortCriterion("Nota", lambda g: _present(g.get("score")), True),
    "played_hours": SortCriterion("Horas jogadas", lambda g: _positive(g.get("played_hours")), True),
    "difficulty": SortCriterion("Dificuldade", lambda g: _present(g.get("difficulty")), True),
    "hltb": SortCriterion("Duração estimada (HLTB)", lambda g: _positive(g.get("hltb_hours")), True),
    "created": SortCriterion("Data de adição", lambda g: _present(g.get("created_at")), True, "date"),
    "hours": SortCriterion("Horas", lambda g: _positive(display_hours(g)), True),
    "name": SortCriterion("Nome", lambda g: fold(g.get("title")), False, "text"),
}

FILTER_FIELDS: Dict[str, str] = {
    "genre": "Gênero",
    "developer": "Desenvolvedora",
    "platform": "Plataforma",
    "franchise": "Franquia / Série",
    "hltb": "Tempo HLTB",
    "plays": "Só jogos rejogados",
    "status": "Status",
    "incomplete": "Só jogos com dados faltando",
}
_COMMON_FILTERS = ("genre", "developer", "platform", "franchise", "hltb", "plays", "incomplete")


@dataclass(frozen=True)
class PageSpec:
    title: str
    sorts: Tuple[str, ...]  # o primeiro é o padrão de fábrica
    filters: Tuple[str, ...] = _COMMON_FILTERS


PAGES: Dict[str, PageSpec] = {
    "game_room": PageSpec("Game Room", ()),
    "queue": PageSpec("Fila", ("name", "hltb", "created")),
    "available": PageSpec("Disponíveis", ("name", "hltb", "created")),
    "finished": PageSpec("Zerados", ("finish_date", "score", "played_hours", "difficulty", "name")),
    "platinum": PageSpec("Platinados", ("platinum_date", "score", "played_hours", "difficulty", "name")),
    "wishlist": PageSpec("Lista de Desejos", ("name", "created")),
    "category": PageSpec("Páginas de categoria", ("name", "score", "hours"), _COMMON_FILTERS + ("status",)),
}


@dataclass
class PageConfig:
    sorts: Tuple[str, ...]        # critérios visíveis, na ordem da página
    default_sort: Optional[str]
    default_descending: bool
    filters: Tuple[str, ...] = field(default_factory=tuple)  # campos do Filtro visíveis


def default_config(page: str) -> PageConfig:
    spec = PAGES[page]
    first = spec.sorts[0] if spec.sorts else None
    return PageConfig(spec.sorts, first, SORT_CRITERIA[first].descending if first else False, spec.filters)


def _key(page: str) -> str:
    return f"pages/{page}"


def normalize(page: str, config: PageConfig) -> PageConfig:
    """Aplica as regras: só critérios/campos da página, ao menos um critério e o padrão entre os visíveis."""
    spec = PAGES[page]
    sorts = tuple(s for s in spec.sorts if s in config.sorts) or spec.sorts[:1]
    default = config.default_sort if config.default_sort in sorts else (sorts[0] if sorts else None)
    descending = bool(config.default_descending) if default == config.default_sort else (
        SORT_CRITERIA[default].descending if default else False)
    filters = tuple(f for f in spec.filters if f in config.filters)
    return PageConfig(sorts, default, descending, filters)


def page_config(page: str) -> PageConfig:
    raw = preferences.settings().value(_key(page))
    if not raw:
        return default_config(page)
    try:
        data = json.loads(str(raw))
        config = PageConfig(tuple(data["sorts"]), data.get("default_sort"), bool(data.get("default_descending")),
                            tuple(data["filters"]))
    except (ValueError, KeyError, TypeError):
        return default_config(page)
    return normalize(page, config)


class _Notifier(QObject):
    changed = Signal(str)  # página alterada


notifier = _Notifier()


def set_page_config(page: str, config: PageConfig) -> PageConfig:
    config = normalize(page, config)
    preferences.settings().setValue(_key(page), json.dumps({
        "sorts": list(config.sorts), "default_sort": config.default_sort,
        "default_descending": config.default_descending, "filters": list(config.filters),
    }))
    notifier.changed.emit(page)
    return config


def reset_all() -> None:
    """Volta todas as páginas ao padrão de fábrica."""
    for page in PAGES:
        preferences.settings().remove(_key(page))
        notifier.changed.emit(page)


def subscribe(page: str, slot) -> None:
    """Chama `slot(config)` (método de um QObject) quando a configuração de `page` muda."""
    preferences.subscribe(notifier.changed, lambda method, changed: method(page_config(page)) if changed == page else None,
                          slot)
