"""Card de jogo pintado com QPainter: zero widgets por card, rolagem e resize fluidos."""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QModelIndex, QPoint, QRect, QRectF, QSettings, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from frontend_desktop import icons
from frontend_desktop.cover_loader import COVER_RADIUS, cover_loader
from frontend_desktop.models.game_list_model import GameRole
from frontend_desktop.styles.tokens import COLORS

PADDING = 10
ROW_GAP = 6
BADGE_H = 18
CARD_RADIUS = 10

CARD_WIDTHS = {"small": 130, "medium": 170, "large": 230}


def _rgba(hex_or_rgba: str) -> QColor:
    """Aceita '#rrggbb' ou 'rgba(r, g, b, a)' (formato usado nos tokens)."""
    if hex_or_rgba.startswith("rgba"):
        r, g, b, a = [p.strip() for p in hex_or_rgba[5:-1].split(",")]
        return QColor(int(r), int(g), int(b), int(float(a) * 255))
    return QColor(hex_or_rgba)


@dataclass(frozen=True)
class CardMetrics:
    card_width: int
    cover_width: int
    cover_height: int
    card_height: int

    @staticmethod
    def for_mode(size_mode: str) -> "CardMetrics":
        width = CARD_WIDTHS.get(size_mode, CARD_WIDTHS["medium"])
        cover_w = width - 2 * PADDING
        cover_h = int(cover_w * 1.5)
        height = PADDING + cover_h + 8 + 18 + ROW_GAP + BADGE_H + ROW_GAP + BADGE_H + PADDING
        return CardMetrics(width, cover_w, cover_h, height)


def current_size_mode() -> str:
    return str(QSettings("GameRoom", "GameRoomLog").value("card_size", "medium"))


def text_color_for(background_hex: str) -> QColor:
    """Preto ou branco conforme a luminância da cor de fundo (badges de gênero)."""
    color = QColor(background_hex)
    if not color.isValid():
        return QColor("#ffffff")
    lum = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
    return QColor("#000000") if lum > 0.62 else QColor("#ffffff")


_PLACEHOLDERS: Dict[Tuple[int, int], QPixmap] = {}


def placeholder_pixmap(width: int, height: int) -> QPixmap:
    key = (width, height)
    if key not in _PLACEHOLDERS:
        pm = QPixmap(width, height)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, width, height), COVER_RADIUS, COVER_RADIUS)
        p.fillPath(path, QColor(COLORS["surface_2"]))
        icon_px = icons.pixmap("gamepad-2", COLORS["text_dim"], 32)
        p.drawPixmap((width - 32) // 2, (height - 32) // 2, 32, 32, icon_px)
        p.end()
        _PLACEHOLDERS[key] = pm
    return _PLACEHOLDERS[key]


class GameCardDelegate(QStyledItemDelegate):
    def __init__(self, size_mode: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.metrics = CardMetrics.for_mode(size_mode or current_size_mode())

    def set_size_mode(self, size_mode: str) -> bool:
        """Retorna True se o tamanho mudou (a view precisa refazer o layout)."""
        new = CardMetrics.for_mode(size_mode)
        changed = new != self.metrics
        self.metrics = new
        return changed

    def sizeHint(self, option, index) -> QSize:
        return QSize(self.metrics.card_width, self.metrics.card_height)

    # --- pintura ---
    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        game = index.data(GameRole)
        if not game:
            return
        m = self.metrics
        rect = QRect(option.rect.topLeft(), QSize(m.card_width, m.card_height))
        hovered = bool(option.state & QStyle.State_MouseOver)
        focused = bool(option.state & QStyle.State_Selected)

        painter.save()
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)

        # fundo do card
        bg = QColor(COLORS["surface_2"] if hovered or focused else COLORS["surface"])
        border = _rgba(COLORS["accent_border"]) if hovered else QColor(COLORS["border"])
        if focused:
            border = QColor(COLORS["accent"])
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5), CARD_RADIUS, CARD_RADIUS)
        painter.fillPath(path, bg)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)

        # capa
        cover_rect = QRect(rect.x() + PADDING, rect.y() + PADDING, m.cover_width, m.cover_height)
        pixmap = None
        filename = game.get("cover_image")
        if filename:
            pixmap = cover_loader.request(filename, m.cover_width, m.cover_height)
        painter.drawPixmap(cover_rect, pixmap or placeholder_pixmap(m.cover_width, m.cover_height))

        # título
        y = cover_rect.bottom() + 1 + 8
        inner_w = m.card_width - 2 * PADDING
        title_font = QFont(option.font)
        title_font.setPixelSize(12 if m.card_width <= 130 else 13)
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        painter.setPen(QColor(COLORS["text"]))
        title_fm = QFontMetrics(title_font)
        title = title_fm.elidedText(game.get("title") or "Sem título", Qt.ElideRight, inner_w)
        painter.drawText(QRect(rect.x() + PADDING, y, inner_w, 18), Qt.AlignVCenter | Qt.AlignLeft, title)

        # badges: plataforma + gênero
        y += 18 + ROW_GAP
        small = QFont(option.font)
        small.setPixelSize(11)
        small_fm = QFontMetrics(small)
        x = rect.x() + PADDING
        right_limit = rect.x() + PADDING + inner_w

        platform = game.get("platform")
        if platform and platform.get("name"):
            text = small_fm.elidedText(platform["name"], Qt.ElideRight, int(inner_w * 0.5))
            x = self._badge(painter, small, small_fm, x, y, text, QColor(COLORS["surface_3"]), QColor(COLORS["text_muted"]), right_limit)
        genres = game.get("genres") or []
        if genres and genres[0].get("name"):
            gcolor = genres[0].get("color") or "#4f46e5"
            avail = right_limit - x
            if avail > 30:
                text = small_fm.elidedText(genres[0]["name"], Qt.ElideRight, avail - 12)
                self._badge(painter, small, small_fm, x, y, text, QColor(gcolor), text_color_for(gcolor), right_limit)

        # linha de meta: horas + nota
        y += BADGE_H + ROW_GAP
        hours = game.get("played_hours") or game.get("hltb_hours") or 0.0
        painter.drawPixmap(QRect(rect.x() + PADDING, y + (BADGE_H - 12) // 2, 12, 12), icons.pixmap("clock", COLORS["text_muted"], 12))
        painter.setFont(small)
        painter.setPen(QColor(COLORS["text_muted"]))
        painter.drawText(QRect(rect.x() + PADDING + 16, y, inner_w // 2, BADGE_H), Qt.AlignVCenter | Qt.AlignLeft, f"{int(hours)}h")

        score = game.get("score")
        if score is not None:
            score_font = QFont(small)
            score_font.setWeight(QFont.DemiBold)
            fm = QFontMetrics(score_font)
            text = f"{score:.1f}"
            w = fm.horizontalAdvance(text) + 12
            self._badge(painter, score_font, fm, right_limit - w, y, text, _rgba(COLORS["accent_soft"]), QColor(COLORS["accent_text"]), right_limit)

        painter.restore()

    @staticmethod
    def _badge(painter, font, fm, x, y, text, bg: QColor, fg: QColor, right_limit: int) -> int:
        """Desenha um badge e devolve o x seguinte (com espaçamento)."""
        w = fm.horizontalAdvance(text) + 12
        if x + w > right_limit:
            return x
        r = QRectF(x, y, w, BADGE_H)
        path = QPainterPath()
        path.addRoundedRect(r, 4, 4)
        painter.fillPath(path, bg)
        painter.setFont(font)
        painter.setPen(fg)
        painter.drawText(r, Qt.AlignCenter, text)
        return int(x + w + 4)
