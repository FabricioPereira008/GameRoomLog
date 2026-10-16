import io
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from PIL import Image
from backend.app.main import app
from backend.app.core.config import settings
from backend.app.core.net_safety import UnsafeURLError, assert_public_url

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.core.database import Base, get_db

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _db():
    app.dependency_overrides[get_db] = _override_get_db
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


client = TestClient(app)


@pytest.fixture(autouse=True)
def tmp_covers(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "COVERS_DIR", tmp_path)
    return tmp_path


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (20, 30), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_upload_valid_image(tmp_covers):
    r = client.post("/api/v1/uploads/cover", files={"file": ("a.png", _png_bytes(), "image/png")})
    assert r.status_code == 200
    assert (tmp_covers / r.json()["filename"]).exists()


def test_upload_rejects_bad_extension():
    r = client.post("/api/v1/uploads/cover", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400


def test_upload_rejects_fake_image():
    r = client.post("/api/v1/uploads/cover", files={"file": ("a.png", b"not an image", "image/png")})
    assert r.status_code == 400


def test_upload_rejects_oversized(monkeypatch):
    monkeypatch.setattr(settings, "MAX_COVER_BYTES", 10)
    r = client.post("/api/v1/uploads/cover", files={"file": ("a.png", _png_bytes(), "image/png")})
    assert r.status_code == 413


def test_get_cover_not_found_and_traversal(tmp_covers):
    assert client.get("/api/v1/uploads/cover/nope.jpg").status_code == 404
    assert client.get("/api/v1/uploads/cover/..%2Fsecret.txt").status_code in (400, 404)


@pytest.mark.parametrize("url", [
    "ftp://example.com/a.png",
    "http://127.0.0.1:8000/",
    "http://localhost/x",
    "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5/a.png",
])
def test_assert_public_url_blocks(url):
    with pytest.raises(UnsafeURLError):
        assert_public_url(url)


def test_cover_url_blocks_private_address():
    r = client.post("/api/v1/uploads/cover-url", json={"url": "http://127.0.0.1:8000/"})
    assert r.status_code == 400


def test_cover_url_rejects_non_http():
    r = client.post("/api/v1/uploads/cover-url", json={"url": "file:///etc/passwd"})
    assert r.status_code == 400


def test_cors_not_wildcard():
    r = client.options(
        "/api/v1/games/",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "DELETE"},
    )
    assert r.headers.get("access-control-allow-origin") != "*"
    assert "access-control-allow-origin" not in r.headers


def test_auto_cover_game_404():
    r = client.post("/api/v1/uploads/auto-cover-game/9999", json={})
    assert r.status_code == 404
