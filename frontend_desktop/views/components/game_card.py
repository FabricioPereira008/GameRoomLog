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
            self.card_width = 165
            self.cover_height = 95
        elif self.size_mode == "large":
            self.card_width = 270
            self.cover_height = 160
        else:  # medium
            self.card_width = 215
            self.cover_height = 125

        self.setFixedWidth(self.card_width)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 10)
        layout.setSpacing(6)

        # Capa do Jogo
        self.cover_label = QLabel()
        self.cover_label.setFixedHeight(self.cover_height)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("background-color: #12131a; border-radius: 6px;")
        
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
                "background-color: #262938; color: #e2e8f0; border: 1px solid #363b4f; border-radius: 4px; padding: 1px 5px; font-size: 9px;"
            )
            tags_layout.addWidget(plat_badge)

        genres = self.game_data.get("genres", [])
        if genres:
            genre_badge = QLabel(genres[0].get("name"))
            g_color = genres[0].get("color", "#4A5568")
            genre_badge.setStyleSheet(
                f"background-color: {g_color}2b; color: {g_color}; border: 1px solid {g_color}88; border-radius: 4px; padding: 1px 5px; font-size: 9px; font-weight: bold;"
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
                "color: #2cb67d; font-weight: bold; font-size: 11px; background-color: #2cb67d22; border: 1px solid #2cb67d55; padding: 1px 5px; border-radius: 4px;"
            )
            meta_layout.addWidget(score_label)

        layout.addLayout(meta_layout)

    def load_cover(self):
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
                        self.card_width - 16, self.cover_height,
                        Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                    )
                    self.cover_label.setPixmap(scaled)
                    return

        # Placeholder
        pixmap = QPixmap(self.card_width - 16, self.cover_height)
        pixmap.fill(QColor("#151720"))
        painter = QPainter(pixmap)
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
