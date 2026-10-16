import re

from PySide6.QtGui import QPalette

from frontend_desktop import icons, theme
from frontend_desktop.styles.tokens import COLORS


def test_qss_has_no_unresolved_placeholders():
    qss = theme.load_qss()
    assert not re.search(r"\$[a-z_]+", qss), "placeholder sem token"
    assert COLORS["accent"] in qss and "Inter" in qss


def test_unknown_token_fails_loudly():
    import pytest
    with pytest.raises(KeyError):
        theme.build_qss("QWidget { color: $nao_existe; }")


def test_palette_uses_tokens(qapp):
    palette = theme.build_palette()
    assert palette.color(QPalette.Window).name() == COLORS["bg"]
    assert palette.color(QPalette.Highlight).name() == COLORS["accent"]


def test_apply_theme_sets_stylesheet_and_fonts(qapp):
    theme.apply_theme(qapp)
    assert "game-card" in qapp.styleSheet()
    assert theme.load_fonts() is True


def test_icons_render_tinted_and_cached(qapp):
    px = icons.pixmap("trophy", "#ff0000", 18)
    assert not px.isNull() and px.width() == 36  # dpr 2
    image = px.toImage()
    opaque = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()) if image.pixelColor(x, y).alpha() > 200]
    assert opaque and all(c.red() > 200 and c.green() < 60 for c in opaque)
    assert icons.pixmap("trophy", "#ff0000", 18) is px
    assert icons.icon("trophy").isNull() is False


def test_missing_icon_returns_empty_pixmap(qapp):
    assert icons.pixmap("nao-existe", "#fff", 16).toImage().pixelColor(5, 5).alpha() == 0


def test_every_bundled_icon_is_valid_svg(qapp):
    names = [p.stem for p in icons.icons_dir().glob("*.svg")]
    assert len(names) > 30
    for name in names:
        img = icons.pixmap(name, "#ffffff", 16).toImage()
        assert any(img.pixelColor(x, y).alpha() > 0 for x in range(img.width()) for y in range(img.height())), name
