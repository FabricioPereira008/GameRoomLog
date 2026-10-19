import os
import sys
import tempfile
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

# Run Qt in offscreen / headless mode for CI/test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# QSettings dos testes vão para uma pasta temporária, nunca para a configuração real do usuário
_SETTINGS_DIR = tempfile.mkdtemp(prefix="gameroom-test-settings-")
for _fmt in (QSettings.NativeFormat, QSettings.IniFormat):
    QSettings.setPath(_fmt, QSettings.UserScope, _SETTINGS_DIR)

@pytest.fixture(scope="session")
def qapp():
    """Fixture to create and manage the QApplication instance across tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def _no_real_backend(monkeypatch):
    """O singleton `api_client` nunca fala com um backend de verdade (o app pode estar aberto em :8000).

    Chamadas não simuladas falham na hora, como com a API offline; testes do ApiClient usam
    instâncias próprias com `responses`.
    """
    import requests
    from frontend_desktop.api_client.client import api_client

    def offline(*_args, **_kwargs):
        raise requests.ConnectionError("rede desligada nos testes")
    monkeypatch.setattr(api_client._session, "request", offline)
