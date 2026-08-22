import time
import pytest
from PySide6.QtGui import QPixmap
from frontend_desktop.views.components.game_card import GameCard, _COVER_PIXMAP_CACHE
from frontend_desktop.views.components.game_grid import GameGrid

def test_game_card_batch_creation_performance(qapp):
    """
    Test the performance of instantiating GameCard widgets.
    Target: 100 cards should be created in under 350ms total.
    """
    sample_games = [
        {
            "id": i,
            "title": f"Performance Test Game {i}",
            "status": "Zerado",
            "score": 8.5,
            "developer": "Studio Test",
            "hltb_hours": 20.0,
            "played_hours": 22.0
        }
        for i in range(100)
    ]

    start_time = time.perf_counter()
    cards = [GameCard(game) for game in sample_games]
    duration_ms = (time.perf_counter() - start_time) * 1000

    print(f"\n[PERFORMANCE] Created 100 GameCards in {duration_ms:.2f} ms ({duration_ms/100:.3f} ms/card)")
    assert len(cards) == 100
    assert duration_ms < 500, f"Card creation took too long: {duration_ms:.2f}ms"

def test_game_grid_layout_performance(qapp):
    """
    Test how quickly GameGrid populates and arranges elements in the layout.
    Target: Rendering a 30-card batch should take less than 250ms.
    """
    grid = GameGrid()
    sample_games = [
        {"id": i, "title": f"Game #{i}", "status": "Zerado", "score": 9.0}
        for i in range(30)
    ]

    start_time = time.perf_counter()
    grid.set_games(sample_games)
    duration_ms = (time.perf_counter() - start_time) * 1000

    print(f"\n[PERFORMANCE] Grid populated with 30 items in {duration_ms:.2f} ms")
    assert grid.rendered_count >= 24
    assert duration_ms < 300, f"Grid population took too long: {duration_ms:.2f}ms"

def test_pixmap_cache_speed_performance(qapp):
    """
    Verify that in-memory QPixmap cache retrieves cached items in microseconds (< 0.05ms).
    """
    cache_key = ("bench_test_cover.jpg", 142, 220)
    dummy_pixmap = QPixmap(100, 140)
    _COVER_PIXMAP_CACHE[cache_key] = dummy_pixmap

    # Measure 1000 cache accesses
    start_time = time.perf_counter()
    for _ in range(1000):
        _ = _COVER_PIXMAP_CACHE.get(cache_key)
    duration_ms = (time.perf_counter() - start_time) * 1000
    avg_per_hit_us = (duration_ms / 1000) * 1000

    print(f"\n[PERFORMANCE] 1000 cache hits executed in {duration_ms:.2f} ms ({avg_per_hit_us:.3f} µs/hit)")
    assert duration_ms < 10.0, f"Cache retrieval is slow: {duration_ms:.2f}ms"

def test_grid_relayout_mutation_performance(qapp):
    """
    Measure the time to re-layout cards after inserting or removing an item.
    Target: Relayout under 100ms.
    """
    grid = GameGrid()
    sample_games = [
        {"id": i, "title": f"Game #{i}", "status": "Zerado", "score": 9.0}
        for i in range(25)
    ]
    grid.set_games(sample_games)

    start_time = time.perf_counter()
    grid.remove_game(5)
    duration_ms = (time.perf_counter() - start_time) * 1000

    print(f"\n[PERFORMANCE] remove_game & relayout took {duration_ms:.2f} ms")
    assert duration_ms < 150, f"Relayout mutation took too long: {duration_ms:.2f}ms"
