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


def subscribe(signal, deliver, slot) -> None:
    """Liga `signal` a `slot` (método de um QObject) via `deliver(method, *args)`.

    Os avisos são globais e vivem mais que os widgets: a ligação guarda só uma referência fraca ao dono e
    é desfeita quando ele é destruído (evita chamar objetos C++ já apagados)."""
    owner = slot.__self__
    method_ref = weakref.WeakMethod(slot)

    def relay(*args) -> None:
        method = method_ref()
        if method is not None and shiboken6.isValid(method.__self__):
            deliver(method, *args)

    signal.connect(relay)

    def drop(*_args) -> None:
        try:
            signal.disconnect(relay)
        except (RuntimeError, TypeError):
            pass

    owner.destroyed.connect(drop)


def subscribe_card_size(slot) -> None:
    """Chama `slot(size)` quando o tamanho dos cards muda (em qualquer tela)."""
    subscribe(notifier.card_size_changed, lambda method, size: method(size), slot)


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


def reset_appearance() -> None:
    """Restaura a aba Aparência: cards médios e páginas de categoria só com concluídos."""
    set_card_size("medium")
    set_category_scope(SCOPE_COMPLETED)


# Versões até a 1.3 guardavam a geometria da janela e a última página; hoje o app sempre abre
# maximizado no Game Room
LEGACY_KEYS = ("window_geometry", "last_view")


def clear_legacy_keys() -> None:
    store = settings()
    for key in LEGACY_KEYS:
        store.remove(key)
