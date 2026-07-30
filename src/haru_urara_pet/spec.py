"""Codex v2 atlas geometry and animation semantics."""

from __future__ import annotations

from dataclasses import dataclass

SPRITE_VERSION = 2
CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 11
ATLAS_WIDTH = CELL_WIDTH * COLUMNS
ATLAS_HEIGHT = CELL_HEIGHT * ROWS
MAX_ATLAS_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class AnimationRow:
    index: int
    name: str
    frame_count: int
    permits_vertical_travel: bool = False
    permits_horizontal_travel: bool = False


ANIMATION_ROWS: tuple[AnimationRow, ...] = (
    AnimationRow(0, "idle", 6),
    AnimationRow(1, "running-right", 8, permits_horizontal_travel=True),
    AnimationRow(2, "running-left", 8, permits_horizontal_travel=True),
    AnimationRow(3, "waving", 4),
    AnimationRow(4, "jumping", 5, permits_vertical_travel=True),
    AnimationRow(5, "failed", 8),
    AnimationRow(6, "waiting", 6),
    AnimationRow(7, "running", 6),
    AnimationRow(8, "review", 6),
    AnimationRow(9, "look-clockwise-a", 8),
    AnimationRow(10, "look-clockwise-b", 8),
)

ROW_BY_NAME = {row.name: row for row in ANIMATION_ROWS}
NEUTRAL_LOOK_FRAME = (0, 6)
ANIMATED_CELL_COUNT = sum(row.frame_count for row in ANIMATION_ROWS)
REQUIRED_CELL_COUNT = ANIMATED_CELL_COUNT + 1
UNUSED_CELL_COUNT = COLUMNS * ROWS - REQUIRED_CELL_COUNT

LOOK_DIRECTIONS: tuple[str, ...] = (
    "000",
    "022.5",
    "045",
    "067.5",
    "090",
    "112.5",
    "135",
    "157.5",
    "180",
    "202.5",
    "225",
    "247.5",
    "270",
    "292.5",
    "315",
    "337.5",
)


def cell_box(row: int, column: int) -> tuple[int, int, int, int]:
    """Return the atlas crop box for a zero-based row and column."""

    left = column * CELL_WIDTH
    top = row * CELL_HEIGHT
    return left, top, left + CELL_WIDTH, top + CELL_HEIGHT


def is_required_cell(row: int, column: int) -> bool:
    """Return whether a grid slot is populated by the v2 contract."""

    if not 0 <= row < ROWS or not 0 <= column < COLUMNS:
        return False
    return (
        column < ANIMATION_ROWS[row].frame_count
        or (row, column) == NEUTRAL_LOOK_FRAME
    )
