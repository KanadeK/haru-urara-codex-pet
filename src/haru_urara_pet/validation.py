"""Strict manifest and atlas validation for Codex v2 pets."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, cast

from PIL import Image, UnidentifiedImageError

from .report import Report
from .spec import (
    ANIMATION_ROWS,
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    COLUMNS,
    MAX_ATLAS_BYTES,
    NEUTRAL_LOOK_FRAME,
    REQUIRED_CELL_COUNT,
    SPRITE_VERSION,
    UNUSED_CELL_COUNT,
    cell_box,
    is_required_cell,
)

MIN_VISIBLE_PIXELS = 32
CHROMA_DISTANCE = 18


def _safe_relative_path(value: object) -> PurePosixPath | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or ":" in candidate.parts[0]:
        return None
    return candidate


def _load_manifest(path: Path, report: Report) -> Mapping[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.add(
            "error",
            "manifest.missing",
            "pet.json is missing.",
            path,
            "Restore pet.json from the release archive, then rerun validate.",
        )
        return None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report.add(
            "error",
            "manifest.unreadable",
            f"pet.json could not be decoded: {exc}",
            path,
            "Replace pet.json with the release copy; do not hand-edit malformed JSON.",
        )
        return None
    if not isinstance(raw, dict):
        report.add(
            "error",
            "manifest.type",
            "pet.json must contain a JSON object.",
            path,
            "Replace the manifest with a JSON object containing the documented fields.",
        )
        return None
    return raw


def _validate_manifest(manifest: Mapping[str, Any], pet_dir: Path, report: Report) -> Path | None:
    expected_types: dict[str, type[object]] = {
        "id": str,
        "displayName": str,
        "description": str,
        "spriteVersionNumber": int,
        "spritesheetPath": str,
    }
    for key, expected in expected_types.items():
        value = manifest.get(key)
        if not isinstance(value, expected):
            report.add(
                "error",
                f"manifest.{key}.type",
                f"{key} must be {expected.__name__}.",
                pet_dir / "pet.json",
                f"Set {key} to a valid {expected.__name__} value.",
            )

    if manifest.get("spriteVersionNumber") != SPRITE_VERSION:
        report.add(
            "error",
            "manifest.sprite-version",
            f"spriteVersionNumber must be {SPRITE_VERSION}.",
            pet_dir / "pet.json",
            "Use the v2 manifest shipped by this release.",
        )

    pet_id = manifest.get("id")
    if isinstance(pet_id, str) and (
        not pet_id or pet_id.strip() != pet_id or "/" in pet_id or "\\" in pet_id
    ):
        report.add(
            "error",
            "manifest.id",
            "id must be a non-empty folder-safe slug.",
            pet_dir / "pet.json",
            "Use a lowercase hyphenated id such as haru-urara.",
        )

    relative = _safe_relative_path(manifest.get("spritesheetPath"))
    if relative is None:
        report.add(
            "error",
            "manifest.spritesheet-path",
            "spritesheetPath must be a safe path inside the pet directory.",
            pet_dir / "pet.json",
            'Set spritesheetPath to "spritesheet.webp".',
        )
        return None

    resolved_root = pet_dir.resolve()
    resolved_atlas = (pet_dir / Path(*relative.parts)).resolve()
    if resolved_atlas != resolved_root and resolved_root not in resolved_atlas.parents:
        report.add(
            "error",
            "manifest.spritesheet-escape",
            "spritesheetPath resolves outside the pet directory.",
            pet_dir / "pet.json",
            'Set spritesheetPath to "spritesheet.webp".',
        )
        return None
    return resolved_atlas


def _pixel_distance(rgb: tuple[int, int, int], key: tuple[int, int, int]) -> int:
    return max(abs(rgb[index] - key[index]) for index in range(3))


def _validate_atlas(atlas_path: Path, report: Report, chroma_key: tuple[int, int, int]) -> None:
    try:
        size_bytes = atlas_path.stat().st_size
    except OSError as exc:
        report.add(
            "error",
            "atlas.missing",
            f"Spritesheet is missing or inaccessible: {exc}",
            atlas_path,
            "Restore spritesheet.webp from the release archive.",
        )
        return

    if size_bytes > MAX_ATLAS_BYTES:
        report.add(
            "error",
            "atlas.file-size",
            f"Atlas is {size_bytes} bytes; limit is {MAX_ATLAS_BYTES}.",
            atlas_path,
            "Re-encode as lossless WebP without changing its pixels.",
        )

    try:
        with Image.open(atlas_path) as source:
            source.load()
            image = source.convert("RGBA")
            report.facts["atlas_format"] = source.format
    except (OSError, UnidentifiedImageError) as exc:
        report.add(
            "error",
            "atlas.unreadable",
            f"Spritesheet could not be decoded: {exc}",
            atlas_path,
            "Replace it with the verified release spritesheet.",
        )
        return

    report.facts.update(
        {
            "atlas_path": str(atlas_path),
            "atlas_size": list(image.size),
            "atlas_bytes": size_bytes,
            "required_cells": REQUIRED_CELL_COUNT,
            "unused_cells": UNUSED_CELL_COUNT,
        }
    )
    if image.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        report.add(
            "error",
            "atlas.geometry",
            f"Atlas size is {image.size}; expected {(ATLAS_WIDTH, ATLAS_HEIGHT)}.",
            atlas_path,
            "Use the v2 8x11 atlas with 192x208 cells.",
        )
        return

    hidden_rgb_pixels = 0
    opaque_chroma_pixels = 0
    rgba_pixels = cast(
        tuple[tuple[int, int, int, int], ...],
        image.get_flattened_data(),
    )
    for red, green, blue, alpha in rgba_pixels:
        if alpha == 0 and (red or green or blue):
            hidden_rgb_pixels += 1
        if alpha >= 224 and _pixel_distance((red, green, blue), chroma_key) <= CHROMA_DISTANCE:
            opaque_chroma_pixels += 1

    report.facts["hidden_rgb_pixels"] = hidden_rgb_pixels
    report.facts["opaque_chroma_pixels"] = opaque_chroma_pixels
    if hidden_rgb_pixels:
        report.add(
            "error",
            "atlas.hidden-rgb",
            f"{hidden_rgb_pixels} fully transparent pixels retain hidden RGB.",
            atlas_path,
            "Clear RGB to zero wherever alpha is zero, then rebuild the atlas once.",
        )
    if opaque_chroma_pixels:
        report.add(
            "error",
            "atlas.chroma",
            f"{opaque_chroma_pixels} opaque pixels remain close to the chroma key.",
            atlas_path,
            "Run the documented single despill pass and use its validated output.",
        )

    empty_required: list[str] = []
    dirty_unused: list[str] = []
    for row in ANIMATION_ROWS:
        for column in range(COLUMNS):
            cell = image.crop(cell_box(row.index, column))
            alpha_channel = cell.getchannel("A")
            alpha_values = cast(tuple[int, ...], alpha_channel.get_flattened_data())
            visible = sum(value > 8 for value in alpha_values)
            required = is_required_cell(row.index, column)
            state = (
                "neutral-look"
                if (row.index, column) == NEUTRAL_LOOK_FRAME
                else row.name
            )
            label = f"{row.index}:{column} ({state})"
            if required and visible < MIN_VISIBLE_PIXELS:
                empty_required.append(label)
            if not required and alpha_channel.getbbox() is not None:
                dirty_unused.append(label)

    report.facts["empty_required_cells"] = empty_required
    report.facts["dirty_unused_cells"] = dirty_unused
    if empty_required:
        report.add(
            "error",
            "atlas.required-empty",
            f"Required cells are empty: {', '.join(empty_required)}.",
            atlas_path,
            "Restore the complete v2 atlas; do not fill cells by copying another state.",
        )
    if dirty_unused:
        report.add(
            "error",
            "atlas.unused-dirty",
            f"Unused cells are not fully transparent: {', '.join(dirty_unused)}.",
            atlas_path,
            "Clear only the unused slots to transparent black.",
        )


def validate_pet(
    pet_dir: str | Path,
    *,
    chroma_key: tuple[int, int, int] = (0, 0, 255),
) -> Report:
    """Validate one unpacked Codex pet directory."""

    root = Path(pet_dir)
    report = Report(subject=str(root))
    manifest = _load_manifest(root / "pet.json", report)
    if manifest is None:
        return report

    atlas_path = _validate_manifest(manifest, root, report)
    report.facts["manifest"] = dict(manifest)
    if atlas_path is not None:
        _validate_atlas(atlas_path, report, chroma_key)
    return report
