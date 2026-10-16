import logging
import sys

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

from app_logging import setup_logging
from frontend_desktop.theme import apply_theme, setup_live_stylesheet
from frontend_desktop.views.main_window import MainWindow

logger = logging.getLogger(__name__)


def create_app() -> QApplication:
    """Cria a QApplication já com tema, fontes e live reload (dev)."""
    app = QApplication(sys.argv)
    app.setApplicationName("GameRoomLog")
    app.setOrganizationName("GameRoom")
    apply_theme(app)
    setup_live_stylesheet(app)
    return app


def create_main_window(app: QApplication) -> MainWindow:
    window = MainWindow()
    # F5 recarrega os estilos manualmente (útil em desenvolvimento)
    shortcut_f5 = QShortcut(QKeySequence("F5"), window)
    shortcut_f5.activated.connect(lambda: getattr(app, "_force_reload_qss", lambda: None)())
    return window


def main():
    setup_logging()
    app = create_app()
    # Se o backend estiver offline, a janela abre e a barra de status informa (carregamento é assíncrono)
    window = create_main_window(app)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
