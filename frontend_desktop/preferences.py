"""Preferências do usuário salvas neste computador (QSettings)."""
from PySide6.QtCore import QObject, QSettings, Signal

CATEGORY_SCOPE_KEY = "category_scope"
SCOPE_COMPLETED, SCOPE_ALL = "completed", "all"  # páginas de gênero/plataforma/franquia


CARD_SIZE_KEY = "card_size"
CARD_SIZES = ("small", "medium", "large")


class _Notifier(QObject):
    card_size_changed = Signal(str)


# Avisa grades e seletores abertos quando o tamanho dos cards muda (em qualquer tela)
notifier = _Notifier()


def settings() -> QSettings:
    return QSettings("GameRoom", "GameRoomLog")


def category_scope() -> str:
    """"completed" mostra só jogos zerados/platinados nas páginas de categoria; "all" mostra todos."""
    value = str(settings().value(CATEGORY_SCOPE_KEY, SCOPE_COMPLETED))
    return value if value in (SCOPE_COMPLETED, SCOPE_ALL) else SCOPE_COMPLETED


def set_category_scope(scope: str) -> None:
    settings().setValue(CATEGORY_SCOPE_KEY, scope if scope in (SCOPE_COMPLETED, SCOPE_ALL) else SCOPE_COMPLETED)


def card_size() -> str:
    value = str(settings().value(CARD_SIZE_KEY, "medium"))
    return value if value in CARD_SIZES else "medium"


def set_card_size(size: str) -> None:
    size = size if size in CARD_SIZES else "medium"
    if size != card_size():
        settings().setValue(CARD_SIZE_KEY, size)
        notifier.card_size_changed.emit(size)
