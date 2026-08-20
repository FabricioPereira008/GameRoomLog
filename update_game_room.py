import re

file_path = "frontend_desktop/views/components/game_room_view.py"

with open(file_path, "r") as f:
    content = f.read()

# We need to add Próximos, Zerados, and Platinados sections.
# Let's completely replace the section logic inside init_ui.

init_ui_pattern = r"(# --- SEÇÃO: AGORA \(Jogando & Próximos\) ---.*)scroll\.setWidget\(container\)"

new_sections = """# --- FUNÇÃO HELPER PARA CRIAR SEÇÕES ---
        self.sections = {}
        
        def create_section(title, object_name):
            section = QFrame()
            section.setObjectName(object_name)
            section.setProperty("class", "game-section-card")
            section.setAttribute(Qt.WA_StyledBackground, True)
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            
            header = QLabel(title)
            header.setProperty("class", "section-header")
            layout.addWidget(header)
            
            grid = GameGrid()
            layout.addWidget(grid)
            
            container_layout.addWidget(section)
            
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setProperty("class", "divider-line")
            container_layout.addWidget(line)
            
            return grid, section, line

        # Criar as 5 seções solicitadas
        self.grid_now, self.sec_now, self.line_now = create_section("🕹️ Agora (Em Andamento)", "nowPlayingSection")
        self.grid_next, self.sec_next, self.line_next = create_section("⏭️ Próximos", "nextSection")
        self.grid_queue, self.sec_queue, self.line_queue = create_section("📋 Fila de Espera", "queueSection")
        self.grid_finished, self.sec_finished, self.line_finished = create_section("🏆 Zerados", "finishedSection")
        self.grid_platinum, self.sec_platinum, self.line_platinum = create_section("👑 Platinados", "platinumSection")

        # Conectar eventos
        self.grid_now.game_selected.connect(self.game_selected.emit)
        self.grid_next.game_selected.connect(self.game_selected.emit)
        self.grid_queue.game_selected.connect(self.game_selected.emit)
        self.grid_finished.game_selected.connect(self.game_selected.emit)
        self.grid_platinum.game_selected.connect(self.game_selected.emit)

        """

content = re.sub(init_ui_pattern, new_sections + "scroll.setWidget(container)", content, flags=re.DOTALL)

# Update set_games signature
set_games_pattern = r"def set_games\(self, now_games: list, queue_games: list\):.*?self\.queue_grid\.set_games\(queue_games\)"
new_set_games = """def set_games(self, now_games: list, next_games: list, queue_games: list, finished_games: list, platinum_games: list):
        self.grid_now.set_games(now_games)
        self.sec_now.setVisible(bool(now_games))
        self.line_now.setVisible(bool(now_games))
        
        self.grid_next.set_games(next_games)
        self.sec_next.setVisible(bool(next_games))
        self.line_next.setVisible(bool(next_games))
        
        self.grid_queue.set_games(queue_games)
        self.sec_queue.setVisible(bool(queue_games))
        self.line_queue.setVisible(bool(queue_games))
        
        self.grid_finished.set_games(finished_games)
        self.sec_finished.setVisible(bool(finished_games))
        self.line_finished.setVisible(bool(finished_games))
        
        self.grid_platinum.set_games(platinum_games)
        self.sec_platinum.setVisible(bool(platinum_games))
        self.line_platinum.setVisible(bool(platinum_games))"""

content = re.sub(set_games_pattern, new_set_games, content, flags=re.DOTALL)

with open(file_path, "w") as f:
    f.write(content)
print("Updated game_room_view.py")
