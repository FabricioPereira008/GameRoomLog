"""Preferências do usuário salvas neste computador (QSettings)."""
import weakref

import shiboken6
from PySide6.QtCore import QObject, QSettings, Signal

CATEGORY_SCOPE_KEY = "category_scope"
SCOPE_COMPLETED, SCOPE_ALL = "completed", "all"  # páginas de gênero/plataforma/franquia


CARD_SIZE_KEY = "card_size"
CARD_SIZES = ("small", "medium", "large")


class _Notifier(QObject):
    card_size_changed = Signal(str)


# Avisa grades e seletores abertos quando o tamanho dos cards muda (em qualquer tela)
notifier = _Notifier()


def subscribe_card_size(slot) -> None:
    """Chama `slot(size)` (método de um QObject) quando o tamanho dos cards muda.

    O aviso é global e vive mais que os widgets: a ligação guarda só uma referência fraca ao dono e é
    desfeita quando ele é destruído (evita chamar objetos C++ já apagados)."""
    owner = slot.__self__
    method_ref = weakref.WeakMethod(slot)

    def relay(size: str) -> None:
        method = method_ref()
        if method is not None and shiboken6.isValid(method.__self__):
            method(size)

    notifier.card_size_changed.connect(relay)

    def drop(*_args) -> None:
        try:
            notifier.card_size_changed.disconnect(relay)
        except (RuntimeError, TypeError):
            pass

    owner.destroyed.connect(drop)


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


WINDOW_GEOMETRY_KEY = "window_geometry"
LAST_VIEW_KEY = "last_view"


def window_geometry():
    return settings().value(WINDOW_GEOMETRY_KEY)


def last_view(default: int = 0) -> int:
    try:
        return int(settings().value(LAST_VIEW_KEY, default))
    except (TypeError, ValueError):
        return default


def save_window_state(geometry, view: int) -> None:
    settings().setValue(WINDOW_GEOMETRY_KEY, geometry)
    settings().setValue(LAST_VIEW_KEY, int(view))
