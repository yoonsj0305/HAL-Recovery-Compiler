from __future__ import annotations

from hal_rc.graph import build_graph, find_path
from hal_rc.models import ChipMap, Tile


def _tile(tile_id, x, y, status="usable"):
    return Tile(tile_id, x, y, status, 0.9, 0.1, 0.1, 0.1)


def test_defective_tiles_excluded_from_graph():
    chip = ChipMap("C", 2, 1, (_tile("A", 0, 0), _tile("B", 1, 0, "defective")))
    graph = build_graph(chip)
    assert "A" in graph.by_id
    assert "B" not in graph.by_id


def test_route_finder_avoids_defective_tiles():
    chip = ChipMap(
        "C", 3, 2,
        (_tile("A", 0, 0), _tile("X", 1, 0, "defective"), _tile("B", 2, 0),
         _tile("C", 0, 1), _tile("D", 1, 1), _tile("E", 2, 1)),
    )
    path = find_path(build_graph(chip), "A", "B")
    assert path == ("A", "C", "D", "E", "B")
    assert "X" not in path


def test_no_route_returned_when_path_blocked():
    chip = ChipMap(
        "C", 3, 1,
        (_tile("A", 0, 0), _tile("X", 1, 0, "defective"), _tile("B", 2, 0)),
    )
    assert find_path(build_graph(chip), "A", "B") is None


def test_weak_gap_obeys_route_policy():
    chip = ChipMap(
        "C", 3, 1,
        (_tile("A", 0, 0), _tile("W", 1, 0, "weak"), _tile("B", 2, 0)),
    )
    graph = build_graph(chip)
    assert find_path(graph, "A", "B", allow_weak=False) is None
    assert find_path(graph, "A", "B", allow_weak=True) == ("A", "W", "B")

