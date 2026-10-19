import pytest

from backend.app.core.config import settings


@pytest.fixture(autouse=True)
def _isolated_covers_dir(tmp_path_factory, monkeypatch):
    """Nenhum teste lê ou apaga capas da pasta real (excluir/trocar capa remove o arquivo sem uso)."""
    monkeypatch.setattr(settings, "COVERS_DIR", tmp_path_factory.mktemp("covers"))
