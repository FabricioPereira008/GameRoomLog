import logging
from datetime import date
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFrame, QScrollArea, QSizePolicy, QGridLayout,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from frontend_desktop.cover_loader import cover_loader
from frontend_desktop.views.components.charts import BarRow, HorizontalBarChart, MonthlyBarChart
from frontend_desktop.views.components.game_card_delegate import placeholder_pixmap
from frontend_desktop.views.components.game_grid import GameGrid, MODE_FULL
from frontend_desktop.views.dialogs.top3_dialog import Top3Dialog
from frontend_desktop.api_client.client import api_client
from frontend_desktop.workers import run_async
from frontend_desktop import icons
from frontend_desktop.styles.tokens import COLORS

logger = logging.getLogger(__name__)

class StatCard(QFrame):
    def __init__(self, title: str, value: str, icon: str = "gamepad-2", parent=None):
        super().__init__(parent)
        self.setProperty("class", "stat-card")
        self.setFixedHeight(62)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Ícone em badge compacto
        icon_box = QFrame()
        icon_box.setProperty("class", "stat-icon-box")
        icon_box.setFixedSize(38, 38)
        icon_layout = QVBoxLayout(icon_box)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)
        
        icon_label = QLabel()
        icon_label.setPixmap(icons.pixmap(icon, COLORS["accent_text"], 20))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)
        
        layout.addWidget(icon_box)

        # Informações de Valor e Rótulo
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(1)
        info_layout.setAlignment(Qt.AlignVCenter)

        self.val_label = QLabel(value)
        self.val_label.setProperty("class", "stat-value")
        info_layout.addWidget(self.val_label)

        self.title_label = QLabel(title)
        self.title_label.setProperty("class", "stat-label")
        info_layout.addWidget(self.title_label)

        layout.addLayout(info_layout)
        layout.addStretch()

    def set_value(self, val: str):
        self.val_label.setText(val)

    def set_title(self, title: str):
        self.title_label.setText(title)


RANK_COLORS = ("#fbbf24", "#cbd5e1", "#d97706")  # ouro, prata, bronze
PODIUM_COVER = {1: (150, 225), 2: (116, 174), 3: (116, 174)}


def hours_text(hours) -> str:
    return f"{int(round(hours or 0))}h"


class PodiumCard(QFrame):
    """Um lugar do pódio: capa, posição, título, nota e horas. Clique abre o jogo."""
    clicked = Signal(dict)

    def __init__(self, place: int, parent=None):
        super().__init__(parent)
        self.place = place
        self.game: dict = {}
        self.setProperty("class", "podium-card")
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
        self.rank = QLabel(f"{place}º")
        self.rank.setAlignment(Qt.AlignCenter)
        self.rank.setFixedSize(34, 34)
        self.rank.setStyleSheet(
            f"color: #0b0c10; background-color: {RANK_COLORS[place - 1]}; border-radius: 17px; font-weight: 800;")
        layout.addWidget(self.rank, 0, Qt.AlignHCenter)
        w, h = PODIUM_COVER[place]
        self.cover = QLabel()
        self.cover.setFixedSize(w, h)
        self.cover.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.cover, 0, Qt.AlignHCenter)
        self.title = QLabel("")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        self.title.setFixedWidth(max(w + 40, 170))
        self.title.setProperty("class", "podium-title")
        layout.addWidget(self.title, 0, Qt.AlignHCenter)
        self.meta = QLabel("")
        self.meta.setAlignment(Qt.AlignCenter)
        self.meta.setProperty("class", "status-muted")
        layout.addWidget(self.meta, 0, Qt.AlignHCenter)
        cover_loader.loaded.connect(self._on_cover_loaded)

    def set_game(self, game: Optional[dict]) -> None:
        self.game = game or {}
        self.setVisible(bool(game))
        if not game:
            return
        self.title.setText(game.get("title") or "")
        score = game.get("score")
        parts = ([f"Nota {score:g}"] if score is not None else []) + [hours_text(game.get("played_hours") or game.get("hltb_hours"))]
        self.meta.setText(" · ".join(parts))
        self._update_cover()

    def _update_cover(self):
        w, h = PODIUM_COVER[self.place]
        filename = self.game.get("cover_image")
        pixmap = cover_loader.request(filename, w, h) if filename else None
        self.cover.setPixmap(pixmap or placeholder_pixmap(w, h))

    def _on_cover_loaded(self, filename: str):
        if self.game and filename == self.game.get("cover_image"):
            self._update_cover()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.game:
            self.clicked.emit(self.game)
        super().mousePressEvent(event)


class HighlightTile(QFrame):
    """Destaque do ano: rótulo pequeno em cima e o valor (ex.: "Elden Ring · 120h")."""

    def __init__(self, label: str, icon: str, parent=None):
        super().__init__(parent)
        self.setProperty("class", "highlight-tile")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        icon_label = QLabel()
        icon_label.setPixmap(icons.pixmap(icon, COLORS["accent_text"], 18))
        layout.addWidget(icon_label, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(1)
        caption = QLabel(label)
        caption.setProperty("class", "stat-label")
        text.addWidget(caption)
        self.value = QLabel("—")
        self.value.setProperty("class", "highlight-value")
        self.value.setWordWrap(True)
        text.addWidget(self.value)
        layout.addLayout(text, 1)

    def set_value(self, text: str) -> None:
        self.value.setText(text or "—")

class YearbookView(QWidget):
    game_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("yearbookView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.current_year = 2026
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # Scroll Area geral para a página do Anuário
        scroll = QScrollArea()
        scroll.setObjectName("yearbookScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setAttribute(Qt.WA_StyledBackground, True)

        container = QWidget()
        container.setObjectName("yearbookScrollContainer")
        container.setAttribute(Qt.WA_StyledBackground, True)

        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 10, 12, 16)
        container_layout.setSpacing(14)
        container_layout.setAlignment(Qt.AlignTop)

        # 1. Cabeçalho do Anuário com Seletor de Ano
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 0)
        
        header_title = QLabel("Resumo do Ano")
        header_title.setProperty("class", "section-header")
        header.addWidget(header_title)

        header.addStretch()

        year_label = QLabel("Ano:")
        year_label.setProperty("class", "yearbook-year")
        header.addWidget(year_label)

        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(100)
        self.year_combo.currentIndexChanged.connect(self.on_year_changed)
        header.addWidget(self.year_combo)

        container_layout.addLayout(header)

        # 2. Números do ano
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)
        self.card_finished = StatCard("Jogos Zerados", "0", "circle-check")
        self.card_platinums = StatCard("Platinas", "0", "trophy")
        self.card_hours = StatCard("Horas Jogadas", "0h", "clock")
        self.card_avg = StatCard("Média de Nota", "N/A", "star")
        for card in (self.card_finished, self.card_platinums, self.card_hours, self.card_avg):
            stats_layout.addWidget(card)
        container_layout.addLayout(stats_layout)

        # 3. Pódio do ano (top 3)
        podium = self._section("Pódio do ano")
        self.podium_hint = QLabel("")
        self.podium_hint.setProperty("class", "status-muted")
        podium.header.addWidget(self.podium_hint)
        podium.header.addStretch()
        self.btn_top3 = QPushButton("Escolher top 3")
        self.btn_top3.setProperty("class", "small-btn")
        self.btn_top3.setCursor(Qt.PointingHandCursor)
        self.btn_top3.clicked.connect(self.choose_top3)
        podium.header.addWidget(self.btn_top3)
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addStretch()
        self.podium_cards = {place: PodiumCard(place) for place in (1, 2, 3)}
        for place in (2, 1, 3):  # 1º no centro, mais alto
            card = self.podium_cards[place]
            card.clicked.connect(self.game_selected.emit)
            row.addWidget(card, 0, Qt.AlignBottom)
        row.addStretch()
        podium.body.addLayout(row)
        self.podium_empty = QLabel("Nenhum jogo zerado neste ano.")
        self.podium_empty.setProperty("class", "empty-state-text")
        self.podium_empty.setAlignment(Qt.AlignCenter)
        podium.body.addWidget(self.podium_empty)
        container_layout.addWidget(podium)

        # 4. Ritmo do ano + destaques
        row = QHBoxLayout()
        row.setSpacing(14)
        monthly = self._section("Zerados por mês")
        self.monthly_chart = MonthlyBarChart()
        monthly.body.addWidget(self.monthly_chart)
        row.addWidget(monthly, 3)
        highlights = self._section("Destaques")
        grid = QGridLayout()
        grid.setSpacing(10)
        self.tile_longest = HighlightTile("Mais longo", "hourglass")
        self.tile_best = HighlightTile("Melhor nota", "star")
        self.tile_hardest = HighlightTile("Mais difícil", "flag")
        self.tile_studio = HighlightTile("Estúdio do ano", "building-2")
        self.tile_franchise = HighlightTile("Série do ano", "layers")
        self.tile_averages = HighlightTile("Médias por jogo", "timer")
        for i, tile in enumerate((self.tile_longest, self.tile_best, self.tile_hardest,
                                  self.tile_studio, self.tile_franchise, self.tile_averages)):
            grid.addWidget(tile, i // 2, i % 2)
        highlights.body.addLayout(grid)
        row.addWidget(highlights, 2)
        container_layout.addLayout(row)

        # 5. Gêneros e plataformas
        row = QHBoxLayout()
        row.setSpacing(14)
        genres = self._section("Gêneros do ano")
        self.genre_chart = HorizontalBarChart(value_format=lambda v: f"{int(v)}")
        genres.body.addWidget(self.genre_chart)
        genres.body.addStretch()
        row.addWidget(genres, 1)
        platforms = self._section("Horas por plataforma")
        self.platform_chart = HorizontalBarChart(value_format=lambda v: f"{int(round(v))}h")
        platforms.body.addWidget(self.platform_chart)
        platforms.body.addStretch()
        row.addWidget(platforms, 1)
        container_layout.addLayout(row)

        # 6. Jogos finalizados
        self.games_section = self._section("Jogos Finalizados")
        self.games_section.setObjectName("yearbookGamesSection")
        self.sub_label = self.games_section.title
        self.game_grid = GameGrid(mode=MODE_FULL)
        self.game_grid.game_selected.connect(self.game_selected.emit)
        self.games_section.body.addWidget(self.game_grid)
        container_layout.addWidget(self.games_section)

        # Adiciona stretch ao final para ancorar tudo no topo sem vácuo
        container_layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    @staticmethod
    def _section(title: str) -> QFrame:
        """Card de seção com cabeçalho (título + espaço para ações) e corpo."""
        frame = QFrame()
        frame.setProperty("class", "game-section-card")
        frame.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(12)
        frame.header = QHBoxLayout()
        frame.title = QLabel(title)
        frame.title.setProperty("class", "section-header")
        frame.header.addWidget(frame.title)
        layout.addLayout(frame.header)
        frame.body = QVBoxLayout()
        frame.body.setSpacing(10)
        layout.addLayout(frame.body)
        return frame

    def load_data(self):
        run_async(
            self, api_client.get_overall_stats, self._on_overall_loaded,
            lambda msg: logger.error("Erro ao carregar anuário: %s", msg),
        )

    def _on_overall_loaded(self, overall: dict):
        available_years = overall.get("available_years", []) or [date.today().year]

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for y in available_years:
            self.year_combo.addItem(str(y), y)
        self.year_combo.blockSignals(False)
        self.load_year(available_years[0])

    def on_year_changed(self):
        year = self.year_combo.currentData()
        if year:
            self.load_year(year)

    def load_year(self, year: int):
        self._year_seq = getattr(self, "_year_seq", 0) + 1
        seq = self._year_seq
        run_async(
            self, api_client.get_yearbook,
            lambda summary: self._on_year_loaded(seq, year, summary),
            lambda msg: logger.error("Erro ao carregar dados do ano %s: %s", year, msg),
            year,
        )

    def _on_year_loaded(self, seq: int, year: int, summary: dict):
        if seq != self._year_seq:
            return
        self.current_year = year
        self.summary = summary
        fin_count = summary.get("total_games_finished", 0)
        avg = summary.get("average_score")
        self.card_finished.set_value(str(fin_count))
        self.card_finished.set_title(self.compare_text(fin_count, summary.get("previous_year_finished"), year))
        self.card_platinums.set_value(str(summary.get("total_platinums", 0)))
        self.card_hours.set_value(hours_text(summary.get("total_hours_played", 0)))
        self.card_avg.set_value(f"{avg:.1f}/10" if avg is not None else "N/A")

        self._show_podium(summary)
        self.monthly_chart.set_data(summary.get("monthly_finished") or [0] * 12, year)
        self._show_highlights(summary)
        self.genre_chart.set_rows([
            BarRow(g["name"], g["count"], f"{g['name']}: {g['count']} {'jogo' if g['count'] == 1 else 'jogos'} · {hours_text(g.get('hours'))}",
                   g.get("color"))
            for g in summary.get("genres", [])])
        self.platform_chart.set_rows([
            BarRow(p["name"], p.get("hours") or 0, f"{p['name']}: {hours_text(p.get('hours'))} em {p['count']} {'jogo' if p['count'] == 1 else 'jogos'}")
            for p in summary.get("platforms", [])])

        games = summary.get("games", [])
        self.sub_label.setText(f"Jogos Finalizados em {year} ({len(games)} {'jogo' if len(games) == 1 else 'jogos'})")
        self.game_grid.set_games(games)

    @staticmethod
    def compare_text(count: int, previous, year: int) -> str:
        if previous is None:
            return "Jogos Zerados"
        diff = count - previous
        if diff == 0:
            return f"Jogos Zerados · igual a {year - 1}"
        return f"Jogos Zerados · {'+' if diff > 0 else ''}{diff} vs {year - 1}"

    def _show_podium(self, summary: dict):
        top3 = summary.get("top3", [])
        for place, card in self.podium_cards.items():
            card.set_game(top3[place - 1] if len(top3) >= place else None)
        has_games = bool(summary.get("games"))
        self.podium_empty.setVisible(not top3)
        self.btn_top3.setEnabled(has_games)
        if not top3:
            self.podium_hint.setText("")
        elif summary.get("top3_custom"):
            self.podium_hint.setText("Escolhido por você")
        else:
            self.podium_hint.setText("Sugestão pelas notas — escolha o seu")

    def _show_highlights(self, summary: dict):
        def game_text(game, extra):
            return f"{game['title']} · {extra}" if game else ""
        longest, best, hardest = summary.get("longest_game"), summary.get("best_game"), summary.get("hardest_game")
        self.tile_longest.set_value(game_text(longest, hours_text((longest or {}).get("played_hours") or (longest or {}).get("hltb_hours"))))
        self.tile_best.set_value(game_text(best, f"nota {(best or {}).get('score', 0):g}"))
        self.tile_hardest.set_value(game_text(hardest, f"dificuldade {(hardest or {}).get('difficulty', 0):g}"))
        devs, frans = summary.get("developers", []), summary.get("franchises", [])
        plural = lambda n: "jogo" if n == 1 else "jogos"
        self.tile_studio.set_value(f"{devs[0]['name']} · {devs[0]['count']} {plural(devs[0]['count'])}" if devs else "")
        self.tile_franchise.set_value(f"{frans[0]['name']} · {frans[0]['count']} {plural(frans[0]['count'])}" if frans else "")
        parts = []
        if summary.get("average_hours") is not None:
            parts.append(f"{hours_text(summary['average_hours'])} jogadas")
        if summary.get("average_difficulty") is not None:
            parts.append(f"dificuldade {summary['average_difficulty']:g}")
        if summary.get("replays"):
            parts.append(f"{summary['replays']} {'rejogada' if summary['replays'] == 1 else 'rejogadas'}")
        self.tile_averages.set_value(" · ".join(parts))

    def choose_top3(self):
        summary = getattr(self, "summary", None) or {}
        games = summary.get("games", [])
        if not games:
            return
        current = [g["id"] for g in summary.get("top3", [])] if summary.get("top3_custom") else []
        dialog = Top3Dialog(self.current_year, games, current, self)
        if dialog.exec() and dialog.selected_ids is not None:
            self._save_top3(dialog.selected_ids)

    def _save_top3(self, game_ids: list):
        year = self.current_year
        self._year_seq = getattr(self, "_year_seq", 0) + 1
        seq = self._year_seq
        run_async(
            self, api_client.set_yearbook_top3,
            lambda summary: self._on_year_loaded(seq, year, summary),
            lambda msg: QMessageBox.critical(self, "Pódio", f"Não foi possível salvar o pódio: {msg}"),
            year, game_ids,
        )
