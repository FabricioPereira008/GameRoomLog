"""Carregamento assíncrono de capas com cache LRU (nenhum I/O ou escala na thread da UI)."""
import logging
from collections import OrderedDict
from typing import Optional

from PySide6.QtCore import QObject, QRunnable, QRectF, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap

from frontend_desktop.api_client.client import api_client

logger = logging.getLogger(__name__)

COVER_RADIUS = 8
MAX_CACHED_COVERS = 600


def render_cover_image(path: str, width: int, height: int, radius: int = COVER_RADIUS) -> Optional[QImage]:
    """Carrega, escala (cobrindo a área), recorta no centro e arredonda os cantos. Thread-safe (só QImage)."""
    source = QImage(path)
    if source.isNull():
        return None
    scaled = source.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    out = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(clip)
    painter.drawImage((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
    painter.end()
    return out


class _Signals(QObject):
    done = Signal(str, int, int, QImage)  # filename, w, h, imagem (nula se falhou)


class _CoverTask(QRunnable):
    def __init__(self, filename: str, width: int, height: int, signals: _Signals):
        super().__init__()
        self.filename, self.width, self.height, self.signals = filename, width, height, signals

    def run(self):
        image = QImage()
        try:
            path = api_client.get_cover_path(self.filename)
            if path:
                rendered = render_cover_image(path, self.width, self.height)
                if rendered is not None:
                    image = rendered
        except Exception:
            logger.warning("Falha ao carregar capa %s", self.filename, exc_info=True)
        self.signals.done.emit(self.filename, self.width, self.height, image)


class CoverLoader(QObject):
    """Cache LRU de pixmaps de capa. `request()` nunca bloqueia: devolve o pixmap se já está em cache,
    senão agenda o carregamento e emite `loaded(filename)` quando chegar."""
    loaded = Signal(str)

    def __init__(self, max_items: int = MAX_CACHED_COVERS, threads: int = 4):
        super().__init__()
        self._cache: "OrderedDict[tuple, QPixmap]" = OrderedDict()
        self._pending = set()
        self._failed = set()
        self._max_items = max_items
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(threads)
        self._signals = _Signals()
        self._signals.done.connect(self._on_done)

    def request(self, filename: str, width: int, height: int) -> Optional[QPixmap]:
        key = (filename, width, height)
        pixmap = self._cache.get(key)
        if pixmap is not None:
            self._cache.move_to_end(key)
            return pixmap
        if key not in self._pending and key not in self._failed:
            self._pending.add(key)
            self._pool.start(_CoverTask(filename, width, height, self._signals))
        return None

    def _on_done(self, filename: str, width: int, height: int, image: QImage):
        key = (filename, width, height)
        self._pending.discard(key)
        if image.isNull():
            self._failed.add(key)  # evita refazer HTTP a cada repaint; invalidate() libera
            return
        self._cache[key] = QPixmap.fromImage(image)
        while len(self._cache) > self._max_items:
            self._cache.popitem(last=False)
        self.loaded.emit(filename)

    def invalidate(self, filename: Optional[str] = None):
        """Descarta capas em cache (ex.: a capa de um jogo foi trocada)."""
        if filename is None:
            self._cache.clear()
            self._failed.clear()
            return
        for store in (self._cache,):
            for key in [k for k in store if k[0] == filename]:
                store.pop(key, None)
        self._failed = {k for k in self._failed if k[0] != filename}

    def wait_for_done(self, msecs: int = 5000) -> bool:
        return self._pool.waitForDone(msecs)

    def __len__(self):
        return len(self._cache)


cover_loader = CoverLoader()
