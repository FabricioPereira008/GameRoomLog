import sys
import os
import time
import threading
from pathlib import Path

# Garantir que o diretório raiz está no sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uvicorn
import requests
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QKeySequence, QShortcut

from backend.app.main import app as fastapi_app
from frontend_desktop.views.main_window import MainWindow
from frontend_desktop.main_app import setup_live_stylesheet

class EmbeddedBackendServer(threading.Thread):
    """Executa o servidor FastAPI/Uvicorn em uma thread em segundo plano."""
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        super().__init__(daemon=True, name="BackendServerThread")
        self.host = host
        self.port = port
        self.config = uvicorn.Config(
            fastapi_app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False
        )
        self.server = uvicorn.Server(self.config)

    def run(self):
        try:
            self.server.run()
        except Exception as e:
            print(f"[Backend Error] {e}")

    def stop(self):
        self.server.should_exit = True

def is_server_ready(url: str = "http://127.0.0.1:8000/") -> bool:
    try:
        r = requests.get(url, timeout=0.5)
        return r.status_code == 200
    except Exception:
        return False

def main():
    backend_thread = None

    # Se o backend não estiver rodando externamente, inicia o backend embutido
    if not is_server_ready():
        print("⚡ Iniciando backend FastAPI integrado...")
        backend_thread = EmbeddedBackendServer()
        backend_thread.start()

        # Aguardar inicialização com limite de 5 segundos
        start_time = time.time()
        while not is_server_ready() and (time.time() - start_time) < 5.0:
            time.sleep(0.05)

        if is_server_ready():
            print("✓ Backend FastAPI pronto em http://127.0.0.1:8000")
        else:
            print("⚠️ Backend demorou para responder, abrindo interface mesmo assim...")

    # Inicializar aplicação PySide6
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("GameRoomLog")
    app.setOrganizationName("GameRoom")

    setup_live_stylesheet(app)

    window = MainWindow()
    shortcut_f5 = QShortcut(QKeySequence("F5"), window)
    shortcut_f5.activated.connect(lambda: getattr(app, "_force_reload_qss", lambda: None)())

    window.show()

    exit_code = app.exec()

    if backend_thread:
        print("Encerrando servidor backend integrado...")
        backend_thread.stop()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
