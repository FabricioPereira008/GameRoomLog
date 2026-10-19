"""GameDialog: vínculo de uma rejogada com o registro original e histórico de jogadas do jogo."""
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from frontend_desktop.api_client.client import api_client
from frontend_desktop.text_search import fold
from frontend_desktop.workers import run_async

logger = logging.getLogger(__name__)


def brief_label(brief: dict) -> str:
    """Rótulo de um jogo na escolha do original: "Hades (PC, 2020)"."""
    extra = [x for x in (brief.get("platform"), brief.get("completion_year")) if x]
    return f"{brief['title']} ({', '.join(str(x) for x in extra)})" if extra else brief["title"]


def replay_group(briefs: list, game_id, replay_of_id) -> list:
    """Jogadas do mesmo jogo (o original e as rejogadas vinculadas), da mais antiga para a mais recente."""
    root = replay_of_id or game_id
    if root is None:
        return []
    return sorted((b for b in briefs if b["id"] == root or b.get("replay_of_id") == root), key=lambda b: b["id"])


def describe_plays(group: list, current_id=None) -> str:
    """ "1ª: 2020 · Zerado · nota 9  |  2ª (esta): Jogando" """
    parts = []
    for number, play in enumerate(group, start=1):
        details = [str(play["completion_year"])] if play.get("completion_year") else []
        details.append(play.get("status") or "")
        if play.get("score") is not None:
            details.append(f"nota {play['score']:g}")
        mark = " (esta)" if play["id"] == current_id else ""
        parts.append(f"{number}ª{mark}: {' · '.join(d for d in details if d)}")
    return "  |  ".join(parts)


class ReplayLinkMixin:
    """Parte do GameDialog: escolha do original (combo_replay_of) e rótulo com as jogadas do grupo.

    Usa do diálogo: game_data, is_edit, input_title, chk_replay, spin_play_count, combo_replay_of,
    lbl_plays, _briefs e _briefs_loading.
    """

    def load_briefs(self):
        if self._briefs is not None or self._briefs_loading:
            return
        self._briefs_loading = True
        run_async(self, api_client.get_game_briefs, self.apply_briefs, self._on_briefs_failed)

    def _on_briefs_failed(self, message: str):
        self._briefs_loading = False
        logger.warning("Não foi possível carregar a lista de jogos para o vínculo de rejogada: %s", message)

    def apply_briefs(self, briefs: list):
        """Preenche a escolha do original (só registros que não são rejogadas) e o histórico de jogadas."""
        self._briefs_loading = False
        self._briefs = briefs
        own_id = self.game_data.get("id")
        originals = [b for b in briefs if b.get("replay_of_id") is None and b["id"] != own_id]
        self.combo_replay_of.blockSignals(True)
        self.combo_replay_of.clear()
        for brief in originals:
            self.combo_replay_of.addItem(brief_label(brief), brief["id"])
        completer = QCompleter([brief_label(b) for b in originals], self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.combo_replay_of.setCompleter(completer)
        self.combo_replay_of.setCurrentIndex(self.combo_replay_of.findData(self.game_data.get("replay_of_id")))
        self.combo_replay_of.blockSignals(False)
        if self.chk_replay.isChecked() and self.combo_replay_of.currentIndex() < 0:
            self._suggest_original()
        self._update_plays_label()

    def _suggest_original(self):
        """Rejogada nova: pré-seleciona o registro com o mesmo título (ignorando acentos e maiúsculas)."""
        title = fold(self.input_title.text().strip())
        if not title:
            return
        for i in range(self.combo_replay_of.count()):
            brief = next(b for b in self._briefs if b["id"] == self.combo_replay_of.itemData(i))
            if fold(brief["title"]) == title:
                self.combo_replay_of.setCurrentIndex(i)
                return

    def _on_replay_of_changed(self, *_):
        root = self.combo_replay_of.currentData()
        if root is not None and not self.is_edit and self._briefs is not None:
            plays = len(replay_group(self._briefs, None, root))
            self.spin_play_count.setValue(max(2, plays + 1))  # próxima jogada do grupo
        self._update_plays_label()

    def selected_replay_of(self):
        """id do original escolhido; sem a lista carregada, mantém o vínculo que o jogo já tinha."""
        if self.combo_replay_of.count() == 0:
            return self.game_data.get("replay_of_id")
        index = self.combo_replay_of.findText(self.combo_replay_of.currentText().strip(), Qt.MatchFixedString)
        return self.combo_replay_of.itemData(index) if index >= 0 else None

    def _update_plays_label(self):
        if self._briefs is None:
            return
        own_id = self.game_data.get("id")
        root = self.combo_replay_of.currentData() if self.chk_replay.isChecked() else None
        group = replay_group(self._briefs, own_id, root)
        self.lbl_plays.setText(f"Jogadas deste jogo — {describe_plays(group, own_id)}" if len(group) > 1 else "")
        self.lbl_plays.setVisible(len(group) > 1)
