import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont

class GameCard(QFrame):
    clicked = Signal(dict)

    def __init__(self, game_data: dict, parent=None):
        super().__init__(parent)
        self.game_data = game_data
        self.setProperty("class", "game-card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(210)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(8)

        # Capa do Jogo
        self.cover_label = QLabel()
        self.cover_label.setFixedHeight(120)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("background-color: #1a1a20; border-radius: 8px;")
        
        self.load_cover()
        layout.addWidget(self.cover_label)

        # Título
        title_label = QLabel(self.game_data.get("title", "Sem Título"))
        title_label.setProperty("class", "card-title")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # Plataforma e Gênero (Tags)
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(4)

        platform = self.game_data.get("platform")
        if platform:
            plat_badge = QLabel(f"🎮 {platform.get('name')}")
            plat_badge.setStyleSheet(
                "background-color: #333644; color: #fffffe; border-radius: 4px; padding: 2px 6px; font-size: 10px;"
            )
            tags_layout.addWidget(plat_badge)

        genres = self.game_data.get("genres", [])
        if genres:
            genre_badge = QLabel(genres[0].get("name"))
            g_color = genres[0].get("color", "#4A5568")
            genre_badge.setStyleSheet(
                f"background-color: {g_color}33; color: {g_color}; border: 1px solid {g_color}; border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold;"
            )
            tags_layout.addWidget(genre_badge)

        tags_layout.addStretch()
        layout.addLayout(tags_layout)

        # Meta info: Horas e Status
        meta_layout = QHBoxLayout()
        
        # Horas HLTB ou Jogadas
        hours = self.game_data.get("played_hours") or self.game_data.get("hltb_hours") or 0.0
        hours_label = QLabel(f"⏱️ {int(hours) if hours.is_integer() else hours}h")
        hours_label.setStyleSheet("color: #94a1b2; font-size: 11px;")
        meta_layout.addWidget(hours_label)

        meta_layout.addStretch()

        # Nota (se tiver)
        score = self.game_data.get("score")
        if score is not None:
            score_label = QLabel(f"⭐ {int(score) if score.is_integer() else score}/10")
            score_label.setStyleSheet(
                "color: #2cb67d; font-weight: bold; font-size: 11px; background-color: #2cb67d22; padding: 1px 5px; border-radius: 4px;"
            )
            meta_layout.addWidget(score_label)

        layout.addLayout(meta_layout)

    def load_cover(self):
        cover_image = self.game_data.get("cover_image")
        if cover_image:
            # Tentar carregar imagem do diretório de armazenamento
            storage_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "backend", "storage", "covers", cover_image)
            if os.path.exists(storage_path):
                pixmap = QPixmap(storage_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(190, 120, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    self.cover_label.setPixmap(scaled)
                    return

        # Placeholder estilizado quando não tem imagem
        pixmap = QPixmap(190, 120)
        pixmap.fill(QColor("#1f2028"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#72757e"))
        font = QFont("Segoe UI", 16)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "🎮")
        painter.end()
        self.cover_label.setPixmap(pixmap)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.game_data)
        super().mousePressEvent(event)
