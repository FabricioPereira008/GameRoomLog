import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from frontend_desktop.views.main_window import MainWindow
from frontend_desktop.api_client.client import api_client

def load_stylesheet(app: QApplication):
    qss_path = Path(__file__).parent / "styles" / "dark_theme.qss"
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GameRoomLog")
    app.setOrganizationName("GameRoom")

    # Carregar folha de estilos Dark Theme
    load_stylesheet(app)

    # Verificar conexão com o Backend
    if not api_client.is_backend_online():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Aviso de Conexão")
        msg.setText("O servidor backend não parece estar rodando em http://127.0.0.1:8000.")
        msg.setInformativeText("Certifique-se de iniciar o backend executando:\npython backend/run_server.py\n\nDeseja continuar mesmo assim?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec() == QMessageBox.No:
            sys.exit(0)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
