import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from frontend_desktop.views.main_window import MainWindow
from frontend_desktop.api_client.client import api_client

def setup_live_stylesheet(app: QApplication):
    qss_path = Path(__file__).parent / "styles" / "dark_theme.qss"
    last_mtime = [0.0]

    def reload_qss():
        if not qss_path.exists():
            return
        try:
            current_mtime = os.path.getmtime(qss_path)
            if current_mtime != last_mtime[0]:
                last_mtime[0] = current_mtime
                with open(qss_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Resetar e reaplicar para forçar recálculo completo
                app.setStyleSheet("")
                app.setStyleSheet(content)
                
                # Forçar repolimento em todos os widgets abertos na tela
                for widget in app.allWidgets():
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                    widget.update()
                
                print("[QSS Live Reload] Estilos atualizados instantaneamente sem reiniciar!")
        except Exception as e:
            print(f"[QSS Live Reload] Erro ao ler estilos: {e}")

    # Primeira carga
    reload_qss()

    # Timer com verificação de mtime a cada 200ms
    timer = QTimer()
    timer.setInterval(200)
    timer.timeout.connect(reload_qss)
    timer.start()
    app._qss_timer = timer
    app._force_reload_qss = reload_qss

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("GameRoomLog")
    app.setOrganizationName("GameRoom")

    # Ativar Live Reload da folha de estilos
    setup_live_stylesheet(app)

    # Verificação não-bloqueante do Backend (sem pop-up irritante)
    if not api_client.is_backend_online():
        print("⚠️  Backend offline em http://127.0.0.1:8000. Abrindo interface em modo offline...")

    window = MainWindow()
    
    # Atalho F5 para recarregar estilos manualmente a qualquer momento
    shortcut_f5 = QShortcut(QKeySequence("F5"), window)
    shortcut_f5.activated.connect(lambda: getattr(app, "_force_reload_qss", lambda: None)())

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
