import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QSettings
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont

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
        self.cover_label.setStyleSheet("background-color: #12131a; border-radius: 8px;")
        
        self.load_cover()
        layout.addWidget(self.cover_label)

        # Título
        title_label = QLabel(self.game_data.get("title", "Sem Título"))
        title_label.setProperty("class", "card-title")
        title_label.setWordWrap(True)
        if self.size_mode == "small":
            title_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #ffffff;")
        elif self.size_mode == "large":
            title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title_label)

        # Tags: Plataforma e Gênero
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(4)

        platform = self.game_data.get("platform")
        if platform:
            plat_badge = QLabel(f"🎮 {platform.get('name')}")
            plat_badge.setStyleSheet(
                "background-color: #262938; color: #e2e8f0; border: 1px solid #363b4f; border-radius: 4px; padding: 2px 6px; font-size: 9px;"
            )
            tags_layout.addWidget(plat_badge)

        genres = self.game_data.get("genres", [])
        if genres:
            genre_badge = QLabel(genres[0].get("name"))
            g_color = genres[0].get("color", "#4f46e5")
            
            # Calcular alto contraste para o texto
            text_color = "#ffffff"
            try:
                clean_hex = g_color.lstrip("#")
                if len(clean_hex) == 6:
                    r, g, b = int(clean_hex[0:2], 16), int(clean_hex[2:4], 16), int(clean_hex[4:6], 16)
                    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                    text_color = "#000000" if lum > 0.62 else "#ffffff"
            except Exception:
                pass

            genre_badge.setStyleSheet(
                f"background-color: {g_color}; color: {text_color}; border-radius: 4px; padding: 2px 6px; font-size: 9px; font-weight: bold;"
            )
            tags_layout.addWidget(genre_badge)

        tags_layout.addStretch()
        layout.addLayout(tags_layout)


        # Meta info: Horas e Nota
        meta_layout = QHBoxLayout()
        hours = self.game_data.get("played_hours") or self.game_data.get("hltb_hours") or 0.0
        hours_label = QLabel(f"⏱️ {int(hours)}h")
        hours_label.setStyleSheet("color: #94a1b2; font-size: 11px;")
        meta_layout.addWidget(hours_label)

        meta_layout.addStretch()

        score = self.game_data.get("score")
        if score is not None:
            score_label = QLabel(f"⭐ {score:.1f}")
            score_label.setStyleSheet(
                "color: #2cb67d; font-weight: bold; font-size: 11px; background-color: #2cb67d22; border: 1px solid #2cb67d55; padding: 2px 6px; border-radius: 4px;"
            )
            meta_layout.addWidget(score_label)

        layout.addLayout(meta_layout)

    def load_cover(self):
        from PySide6.QtGui import QPainterPath
        
        target_width = self.card_width - 28
        cover_image = self.game_data.get("cover_image")
        
        if cover_image:
            storage_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "backend", "storage", "covers", cover_image
            )
            if os.path.exists(storage_path):
                pixmap = QPixmap(storage_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        target_width, self.cover_height,
                        Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                    )
                    
                    rounded = QPixmap(target_width, self.cover_height)
                    rounded.fill(Qt.transparent)
                    painter = QPainter(rounded)
                    painter.setRenderHint(QPainter.Antialiasing)
                    path = QPainterPath()
                    path.addRoundedRect(0, 0, target_width, self.cover_height, 8, 8)
                    painter.setClipPath(path)
                    
                    x_offset = (target_width - scaled.width()) // 2
                    y_offset = (self.cover_height - scaled.height()) // 2
                    painter.drawPixmap(x_offset, y_offset, scaled)
                    painter.end()
                    
                    self.cover_label.setPixmap(rounded)
                    return

        # Placeholder
        pixmap = QPixmap(target_width, self.cover_height)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, target_width, self.cover_height, 8, 8)
        painter.setClipPath(path)
        painter.fillPath(path, QColor("#151720"))
        painter.setPen(QColor("#525875"))
        font = QFont("Segoe UI", 16)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "🎮")
        painter.end()
        self.cover_label.setPixmap(pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.game_data)
        super().mousePressEvent(event)
