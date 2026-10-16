from typing import Optional
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QSettings
from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath
from frontend_desktop.api_client.client import api_client
from frontend_desktop import icons
from frontend_desktop.styles.tokens import COLORS

_COVER_PIXMAP_CACHE = {}
_PLACEHOLDER_CACHE = {}

def resolve_cover_path(cover_image: str) -> Optional[str]:
    """Obtém a capa via ApiClient (cache local em disco); None se indisponível."""
    return api_client.get_cover_path(cover_image)

def get_cached_cover_pixmap(cover_image: str, target_width: int, target_height: int) -> QPixmap:
    """Carrega, escala e arredonda a capa com cache em memória para rolagem 100% fluida."""
    cache_key = (cover_image, target_width, target_height)
    if cache_key in _COVER_PIXMAP_CACHE:
        return _COVER_PIXMAP_CACHE[cache_key]

    storage_path = resolve_cover_path(cover_image)
    if not storage_path:
        return None

    pixmap = QPixmap(storage_path)
    if pixmap.isNull():
        return None

    scaled = pixmap.scaled(
        target_width, target_height,
        Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
    )
    
    rounded = QPixmap(target_width, target_height)
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, target_width, target_height, 8, 8)
    painter.setClipPath(path)
    
    x_offset = (target_width - scaled.width()) // 2
    y_offset = (target_height - scaled.height()) // 2
    painter.drawPixmap(x_offset, y_offset, scaled)
    painter.end()

    _COVER_PIXMAP_CACHE[cache_key] = rounded
    return rounded

def get_cached_placeholder_pixmap(target_width: int, target_height: int) -> QPixmap:
    """Retorna placeholder padrão reutilizável."""
    cache_key = (target_width, target_height)
    if cache_key in _PLACEHOLDER_CACHE:
        return _PLACEHOLDER_CACHE[cache_key]

    pixmap = QPixmap(target_width, target_height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, target_width, target_height, 8, 8)
    painter.setClipPath(path)
    painter.fillPath(path, QColor(COLORS["surface_2"]))
    icon_px = icons.pixmap("gamepad-2", COLORS["text_dim"], 32)
    painter.drawPixmap(
        (target_width - 32) // 2, (target_height - 32) // 2, 32, 32, icon_px
    )
    painter.end()

    _PLACEHOLDER_CACHE[cache_key] = pixmap
    return pixmap

def invalidate_cover_cache(cover_image: str = None):
    """Invalida o cache de imagem se a capa for alterada."""
    global _COVER_PIXMAP_CACHE
    if cover_image:
        keys_to_del = [k for k in _COVER_PIXMAP_CACHE if k[0] == cover_image]
        for k in keys_to_del:
            _COVER_PIXMAP_CACHE.pop(k, None)
    else:
        _COVER_PIXMAP_CACHE.clear()


class GameCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, game_data: dict, size_mode: str = None, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.size_mode = size_mode or QSettings("GameRoom", "GameRoomLog").value("card_size", "medium")
        self.setProperty("class", "game-card")
        self.setCursor(Qt.PointingHandCursor)
        
        if self.size_mode == "small":
            self.card_width = 130
            self.cover_height = 160
        elif self.size_mode == "large":
            self.card_width = 230
            self.cover_height = 310
        else:  # medium
            self.card_width = 170
            self.cover_height = 220

        self.setFixedWidth(self.card_width)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # Capa do Jogo
        self.cover_label = QLabel()
        self.cover_label.setFixedHeight(self.cover_height)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setProperty("class", "cover")
        
        self.load_cover()
        layout.addWidget(self.cover_label)

        # Título
        self.title_label = QLabel(self.game_data.get("title", "Sem Título"))
        self.title_label.setProperty("class", "card-title")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        # Tags: Plataforma e Gênero
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setSpacing(4)
        layout.addLayout(self.tags_layout)
        self.render_tags()

        # Meta info: Horas e Nota
        self.meta_layout = QHBoxLayout()
        self.meta_layout.setSpacing(4)
        self.hours_icon = QLabel()
        self.hours_icon.setPixmap(icons.pixmap("clock", COLORS["text_muted"], 12))
        self.meta_layout.addWidget(self.hours_icon)
        self.hours_label = QLabel()
        self.hours_label.setProperty("class", "card-meta")
        self.meta_layout.addWidget(self.hours_label)
        self.meta_layout.addStretch()

        self.score_label = QLabel()
        self.score_label.setProperty("class", "badge-score")
        self.meta_layout.addWidget(self.score_label)
        layout.addLayout(self.meta_layout)

        self.render_meta()

    def render_tags(self):
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        platform = self.game_data.get("platform")
        if platform:
            plat_badge = QLabel(platform.get("name"))
            plat_badge.setProperty("class", "badge")
            self.tags_layout.addWidget(plat_badge)

        genres = self.game_data.get("genres", [])
        if genres:
            genre_badge = QLabel(genres[0].get("name"))
            g_color = genres[0].get("color", "#4f46e5")
            
            text_color = "#ffffff"
            try:
                clean_hex = g_color.lstrip("#")
                if len(clean_hex) == 6:
                    r, g, b = int(clean_hex[0:2], 16), int(clean_hex[2:4], 16), int(clean_hex[4:6], 16)
                    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    text_color = "#000000" if lum > 0.62 else "#ffffff"
            except Exception:
                pass

            genre_badge.setProperty("class", "badge-genre")
            # Única cor dinâmica (vem do dado do gênero); forma e tipografia ficam no QSS
            genre_badge.setStyleSheet(f"background-color: {g_color}; color: {text_color};")
            self.tags_layout.addWidget(genre_badge)

        self.tags_layout.addStretch()

    def render_meta(self):
        hours = self.game_data.get("played_hours") or self.game_data.get("hltb_hours") or 0.0
        self.hours_label.setText(f"{int(hours)}h")

        score = self.game_data.get("score")
        if score is not None:
            self.score_label.setText(f"{score:.1f}")
            self.score_label.setVisible(True)
        else:
            self.score_label.setVisible(False)

    def update_data(self, new_data: dict):
        """Atualiza os dados e visual do card in-place sem recriar o widget."""
        old_cover = self.game_data.get("cover_image")
        new_cover = new_data.get("cover_image")
        if old_cover != new_cover:
            invalidate_cover_cache(old_cover)
            invalidate_cover_cache(new_cover)

        self.game_data = new_data
        self.title_label.setText(new_data.get("title", "Sem Título"))
        self.render_tags()
        self.render_meta()
        self.load_cover()

    def load_cover(self):
        target_width = self.card_width - 28
        cover_image = self.game_data.get("cover_image")
        
        if cover_image:
            cached_pix = get_cached_cover_pixmap(cover_image, target_width, self.cover_height)
            if cached_pix:
                self.cover_label.setPixmap(cached_pix)
                return

        self.cover_label.setPixmap(get_cached_placeholder_pixmap(target_width, self.cover_height))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.game_data)
        super().mousePressEvent(event)


class LoadMoreCard(QFrame):
    """Card botão com '+' no centro para carregar mais itens de uma categoria."""
    clicked = Signal()

    def __init__(self, size_mode: str = None, parent=None):
        super().__init__(parent)
        self.size_mode = size_mode or QSettings("GameRoom", "GameRoomLog").value("card_size", "medium")
        self.setProperty("class", "game-card load-more-card")
        self.setCursor(Qt.PointingHandCursor)
        
        if self.size_mode == "small":
            self.card_width = 130
            self.cover_height = 160
        elif self.size_mode == "large":
            self.card_width = 230
            self.cover_height = 310
        else:  # medium
            self.card_width = 170
            self.cover_height = 220

        self.setFixedWidth(self.card_width)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        # Bloco visual que simula a capa
        cover_box = QFrame()
        cover_box.setFixedHeight(self.cover_height)
        box_layout = QVBoxLayout(cover_box)
        box_layout.setAlignment(Qt.AlignCenter)
        box_layout.setSpacing(6)

        plus_icon = QLabel()
        plus_icon.setAlignment(Qt.AlignCenter)
        plus_icon.setPixmap(icons.pixmap("plus", COLORS["accent_text"], 28))
        box_layout.addWidget(plus_icon)

        more_text = QLabel("Carregar mais")
        more_text.setAlignment(Qt.AlignCenter)
        more_text.setProperty("class", "load-more-title")
        box_layout.addWidget(more_text)

        layout.addWidget(cover_box)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
