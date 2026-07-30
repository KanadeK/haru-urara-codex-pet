from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from haru_urara_pet.spec import (
    ANIMATION_ROWS,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    NEUTRAL_LOOK_FRAME,
    cell_box,
)


def make_pet(
    root: Path,
    *,
    outline: tuple[int, int, int] = (98, 40, 68),
    fill: tuple[int, int, int] = (242, 128, 164),
    animate: bool = True,
    image_format: str = "WEBP",
) -> Path:
    pet_dir = root / "haru-urara"
    pet_dir.mkdir(parents=True)
    atlas = Image.new("RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (0, 0, 0, 0))
    for row in ANIMATION_ROWS:
        for column in range(row.frame_count):
            left, top, _right, _bottom = cell_box(row.index, column)
            horizontal = (column % 3) - 1 if animate else 0
            vertical = -(column % 3) * 7 if animate and row.permits_vertical_travel else 0
            frame = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
            draw = ImageDraw.Draw(frame)
            draw.ellipse(
                (46 + horizontal, 42 + vertical, 146 + horizontal, 160 + vertical),
                fill=(*fill, 255),
                outline=(*outline, 255),
                width=8,
            )
            draw.rectangle(
                (72 + horizontal, 146 + vertical, 120 + horizontal, 190 + vertical),
                fill=(252, 244, 238, 255),
                outline=(*outline, 255),
                width=6,
            )
            eye_shift = (column % 4) * 2 if animate else 0
            draw.ellipse(
                (76 + eye_shift, 82 + vertical, 88 + eye_shift, 96 + vertical),
                fill=(255, 255, 255, 255),
            )
            draw.ellipse(
                (80 + eye_shift, 85 + vertical, 86 + eye_shift, 93 + vertical),
                fill=(60, 25, 45, 255),
            )
            atlas.alpha_composite(frame, (left, top))
    neutral = atlas.crop(cell_box(0, 0)).copy()
    neutral_row, neutral_column = NEUTRAL_LOOK_FRAME
    neutral_left, neutral_top, _right, _bottom = cell_box(
        neutral_row,
        neutral_column,
    )
    atlas.alpha_composite(neutral, (neutral_left, neutral_top))
    manifest = {
        "id": "haru-urara",
        "displayName": "Haru Urara",
        "description": "A fixture pet.",
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.webp",
    }
    (pet_dir / "pet.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if image_format == "WEBP":
        atlas.save(pet_dir / "spritesheet.webp", "WEBP", lossless=True, method=6, exact=True)
    else:
        atlas.save(pet_dir / "spritesheet.webp", image_format)
    return pet_dir


@pytest.fixture
def pet_factory(tmp_path: Path) -> Callable[..., Path]:
    counter = 0

    def factory(**kwargs: object) -> Path:
        nonlocal counter
        counter += 1
        return make_pet(tmp_path / f"fixture-{counter}", **kwargs)  # type: ignore[arg-type]

    return factory
