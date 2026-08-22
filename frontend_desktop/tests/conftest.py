import os
import sys
import pytest
from PySide6.QtWidgets import QApplication

# Run Qt in offscreen / headless mode for CI/test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

@pytest.fixture(scope="session")
def qapp():
    """Fixture to create and manage the QApplication instance across tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
