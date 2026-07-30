from haru_urara_pet.spec import (
    ANIMATION_ROWS,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    NEUTRAL_LOOK_FRAME,
    REQUIRED_CELL_COUNT,
    UNUSED_CELL_COUNT,
    cell_box,
    is_required_cell,
)


def test_v2_geometry_and_counts() -> None:
    assert (ATLAS_WIDTH, ATLAS_HEIGHT) == (1536, 2288)
    assert REQUIRED_CELL_COUNT == 74
    assert UNUSED_CELL_COUNT == 14
    assert [row.frame_count for row in ANIMATION_ROWS] == [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]


def test_cell_helpers_reject_out_of_range() -> None:
    assert cell_box(1, 2) == (384, 208, 576, 416)
    assert is_required_cell(0, 5)
    assert NEUTRAL_LOOK_FRAME == (0, 6)
    assert is_required_cell(0, 6)
    assert not is_required_cell(0, 7)
    assert not is_required_cell(-1, 0)
    assert not is_required_cell(11, 0)
