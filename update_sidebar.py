import re

file_path = "frontend_desktop/views/components/sidebar.py"
with open(file_path, "r") as f:
    content = f.read()

# Replace the nav_items list
old_nav_items = """nav_items = [
            ("🕹️  Game Room", 0),
            ("📋  Fila de Espera", 1),
            ("🏆  Zerados", 2),
            ("👑  Platinados", 3),
            ("📊  Anuário", 4),
            ("🎨  Gêneros", 5),
            ("🎮  Plataformas", 6),
            ("👾  Séries / Franquias", 7),
            ("📚  Biblioteca (Tabela)", 8),
            ("⭐  Lista de Desejos", 9)
        ]"""

new_nav_items = """nav_items = [
            ("🕹️  Game Room", 0),
            ("📋  Fila de Espera", 1),
            ("🟢  Disponíveis", 10),
            ("🏆  Zerados", 2),
            ("👑  Platinados", 3),
            ("📊  Anuário", 4),
            ("🎨  Gêneros", 5),
            ("🎮  Plataformas", 6),
            ("👾  Séries / Franquias", 7),
            ("📚  Biblioteca (Tabela)", 8),
            ("⭐  Lista de Desejos", 9)
        ]"""

content = content.replace(old_nav_items, new_nav_items)
with open(file_path, "w") as f:
    f.write(content)
print("Sidebar updated.")
