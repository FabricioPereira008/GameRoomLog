import pytest
from datetime import date
from backend.app.models.game import GameStatus, PlayType
from backend.app.services.notion_importer import (
    parse_notion_date, clean_relation, clean_number, clean_play_count, map_status, map_play_type
)

def test_parse_notion_date():
    # DD/MM/YYYY
    assert parse_notion_date("13/04/2024") == date(2024, 4, 13)
    assert parse_notion_date("09/04/2025") == date(2025, 4, 9)
    # Full Portuguese text
    assert parse_notion_date("13 de abril de 2024") == date(2024, 4, 13)
    assert parse_notion_date("11 de fevereiro de 2025") == date(2025, 2, 11)
    assert parse_notion_date("31 de outubro de 2024") == date(2024, 10, 31)
    # Empty
    assert parse_notion_date("") is None
    assert parse_notion_date(None) is None

def test_clean_relation():
    sample = "PC (Game%20Room/Plataformas/Plataformas/PC%201b23b820c620808bb1cdf9d706ae7aa5.md)"
    assert clean_relation(sample) == "PC"

    sample_genre = "Ação/Aventura (Game%20Room/G%C3%AAneros/G%C3%AAneros/A%C3%A7%C3%A3o%20Aventura%201b23b820c62080759c8bf9dc2ae5ac0f.md)"
    assert clean_relation(sample_genre) == "Ação/Aventura"

    plain = "Supergiant Games"
    assert clean_relation(plain) == "Supergiant Games"

def test_clean_number():
    assert clean_number("53") == 53.0
    assert clean_number("53h") == 53.0
    assert clean_number("⏳ 91h") == 91.0
    assert clean_number("9.5") == 9.5
    assert clean_number("") is None

def test_clean_play_count():
    assert clean_play_count("🔂 1° Vez") == 1
    assert clean_play_count("2ª Vez") == 2
    assert clean_play_count(None) == 1

def test_map_play_type():
    assert map_play_type("Re-Jogada") == PlayType.REJOGADA
    assert map_play_type("Rejogada") == PlayType.REJOGADA
    assert map_play_type("Primeira Jogada") == PlayType.PRIMEIRA_JOGADA
    assert map_play_type(None) == PlayType.PRIMEIRA_JOGADA

def test_map_status():
    assert map_status("Zerados") == GameStatus.ZERADO
    assert map_status("Platinados") == GameStatus.PLATINADO
    assert map_status("Disponível") == GameStatus.DISPONIVEL
    assert map_status("Fila") == GameStatus.FILA
    assert map_status("Próximo") == GameStatus.PROXIMO
    assert map_status("Jogando") == GameStatus.JOGANDO
    assert map_status("Pausados") == GameStatus.PAUSADO
    assert map_status("Desisti") == GameStatus.DESISTI
    assert map_status("Lista de Desejos") == GameStatus.WISHLIST
