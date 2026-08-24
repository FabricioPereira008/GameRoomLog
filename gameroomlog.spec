# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

block_cipher = None

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

added_datas = [
    (os.path.join(BASE_DIR, 'frontend_desktop', 'styles', 'dark_theme.qss'), os.path.join('frontend_desktop', 'styles')),
    (os.path.join(BASE_DIR, 'resources'), 'resources'),
]

hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'pydantic',
    'pydantic_settings',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'backend.app.api.v1.api_router',
    'backend.app.api.v1.endpoints.games',
    'backend.app.api.v1.endpoints.genres',
    'backend.app.api.v1.endpoints.platforms',
    'backend.app.api.v1.endpoints.franchises',
    'backend.app.api.v1.endpoints.developers',
    'backend.app.api.v1.endpoints.stats',
    'backend.app.api.v1.endpoints.uploads',
    'backend.app.api.v1.endpoints.imports',
    'backend.app.models.game',
    'backend.app.models.genre',
    'backend.app.models.platform',
    'backend.app.models.franchise',
    'backend.app.models.developer',
    'frontend_desktop.views.main_window',
    'frontend_desktop.views.components.game_room_view',
    'frontend_desktop.views.components.game_grid',
    'frontend_desktop.views.components.game_card',
    'frontend_desktop.views.components.game_table',
    'frontend_desktop.views.components.yearbook_view',
    'frontend_desktop.views.components.management_view',
    'frontend_desktop.views.components.settings_view',
    'frontend_desktop.views.components.category_detail_view',
    'frontend_desktop.views.components.filter_panel',
    'frontend_desktop.views.dialogs.game_dialog',
    'frontend_desktop.views.dialogs.image_cropper_dialog',
]

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[BASE_DIR],
    binaries=[],
    datas=added_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='gameroomlog',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
