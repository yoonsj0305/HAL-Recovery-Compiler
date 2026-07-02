"""Deterministic 2D grid graph and safe route finding."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .models import ChipMap, Route, Tile, TileClassification


@dataclass(frozen=True, slots=True)
class GridGraph:
    chip: ChipMap
    by_id: dict[str, Tile]
    by_coordinate: dict[tuple[int, int], Tile]

    def neighbors(self, tile_id: str, *, allow_weak: bool) -> tuple[str, ...]:
        tile = self.by_id[tile_id]
        candidates: list[Tile] = []
        for coordinate in (
            (tile.x, tile.y - 1),
            (tile.x - 1, tile.y),
            (tile.x + 1, tile.y),
            (tile.x, tile.y + 1),
        ):
            neighbor = self.by_coordinate.get(coordinate)
            if neighbor is None or neighbor.status == "defective":
                continue
            if neighbor.status == "weak" and not allow_weak:
                continue
            candidates.append(neighbor)
        return tuple(candidate.tile_id for candidate in candidates)


def build_graph(chip: ChipMap) -> GridGraph:
    """Build the routing graph; defective tiles are absent by construction."""
    routable = tuple(tile for tile in chip.tiles if tile.status != "defective")
    return GridGraph(
        chip=chip,
        by_id={tile.tile_id: tile for tile in routable},
        by_coordinate={(tile.x, tile.y): tile for tile in routable},
    )


def classify_tiles(chip: ChipMap) -> tuple[TileClassification, ...]:
    output: list[TileClassification] = []
    for tile in sorted(chip.tiles, key=lambda item: (item.y, item.x, item.tile_id)):
        if tile.status == "defective":
            output.append(
                TileClassification(tile.tile_id, "blocked", False, "defective_tile")
            )
        elif tile.status == "weak":
            output.append(
                TileClassification(tile.tile_id, "conditional", True, "weak_policy_gate")
            )
        else:
            output.append(TileClassification(tile.tile_id, "usable", True, "usable_tile"))
    return tuple(output)


def find_path(
    graph: GridGraph,
    start_tile_id: str,
    end_tile_id: str,
    *,
    allow_weak: bool = True,
) -> tuple[str, ...] | None:
    """Return a shortest deterministic BFS path or None when blocked."""
    if start_tile_id not in graph.by_id or end_tile_id not in graph.by_id:
        return None
    if not allow_weak and (
        graph.by_id[start_tile_id].status == "weak"
        or graph.by_id[end_tile_id].status == "weak"
    ):
        return None
    if start_tile_id == end_tile_id:
        return (start_tile_id,)

    queue: deque[str] = deque([start_tile_id])
    previous: dict[str, str | None] = {start_tile_id: None}
    while queue:
        current = queue.popleft()
        for neighbor in graph.neighbors(current, allow_weak=allow_weak):
            if neighbor in previous:
                continue
            previous[neighbor] = current
            if neighbor == end_tile_id:
                path = [neighbor]
                cursor: str | None = current
                while cursor is not None:
                    path.append(cursor)
                    cursor = previous[cursor]
                return tuple(reversed(path))
            queue.append(neighbor)
    return None


def build_assignment_routes(
    graph: GridGraph,
    workload_id: str,
    tile_ids: tuple[str, ...],
    *,
    allow_weak: bool,
) -> tuple[tuple[Route, ...], tuple[Route, ...]]:
    preferred: list[Route] = []
    blocked: list[Route] = []
    for start, end in zip(tile_ids, tile_ids[1:]):
        path = find_path(graph, start, end, allow_weak=allow_weak)
        if path is None:
            blocked.append(
                Route(
                    workload_id=workload_id,
                    start_tile_id=start,
                    end_tile_id=end,
                    tile_ids=(),
                    status="blocked",
                    reason="no_policy_compliant_path",
                )
            )
        else:
            preferred.append(
                Route(
                    workload_id=workload_id,
                    start_tile_id=start,
                    end_tile_id=end,
                    tile_ids=path,
                )
            )
    return tuple(preferred), tuple(blocked)

