from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from haru_urara_pet.spec import ATLAS_HEIGHT, ATLAS_WIDTH, cell_box
from haru_urara_pet.validation import validate_pet


def issue_codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}  # type: ignore[attr-defined]


def test_valid_pet_passes(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    report = validate_pet(pet)
    assert report.ok, report.to_dict()
    assert report.facts["required_cells"] == 74
    assert report.facts["unused_cells"] == 14
    assert report.facts["atlas_size"] == [1536, 2288]


def test_missing_and_malformed_manifest(tmp_path: Path) -> None:
    missing = validate_pet(tmp_path)
    assert "manifest.missing" in issue_codes(missing)
    (tmp_path / "pet.json").write_text("{no", encoding="utf-8")
    malformed = validate_pet(tmp_path)
    assert "manifest.unreadable" in issue_codes(malformed)
    (tmp_path / "pet.json").write_text("[]", encoding="utf-8")
    wrong_type = validate_pet(tmp_path)
    assert "manifest.type" in issue_codes(wrong_type)


def test_manifest_field_types_version_id_and_escape(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    manifest_path = pet / "pet.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "id": "../bad",
            "displayName": 42,
            "description": None,
            "spriteVersionNumber": 1,
            "spritesheetPath": "../outside.webp",
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = validate_pet(pet)
    codes = issue_codes(report)
    assert "manifest.id" in codes
    assert "manifest.displayName.type" in codes
    assert "manifest.description.type" in codes
    assert "manifest.sprite-version" in codes
    assert "manifest.spritesheet-path" in codes


def test_wrong_geometry_is_rejected(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(pet / "spritesheet.webp", "PNG")
    report = validate_pet(pet)
    assert "atlas.geometry" in issue_codes(report)


def test_empty_required_and_dirty_unused_are_rejected(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    with Image.open(pet / "spritesheet.webp") as source:
        atlas = source.convert("RGBA")
    draw = ImageDraw.Draw(atlas)
    draw.rectangle(cell_box(0, 0), fill=(0, 0, 0, 0))
    left, top, right, bottom = cell_box(0, 7)
    draw.rectangle((left + 20, top + 20, right - 20, bottom - 20), fill=(255, 0, 0, 255))
    atlas.save(pet / "spritesheet.webp", "PNG")
    report = validate_pet(pet)
    codes = issue_codes(report)
    assert "atlas.required-empty" in codes
    assert "atlas.unused-dirty" in codes


def test_hidden_rgb_and_opaque_chroma_are_rejected(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    with Image.open(pet / "spritesheet.webp") as source:
        atlas = source.convert("RGBA")
    atlas.putpixel((0, 0), (100, 100, 100, 0))
    atlas.putpixel((80, 80), (0, 0, 255, 255))
    atlas.save(pet / "spritesheet.webp", "PNG")
    report = validate_pet(pet)
    codes = issue_codes(report)
    assert "atlas.hidden-rgb" in codes
    assert "atlas.chroma" in codes


def test_unreadable_and_missing_atlas(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    atlas = pet / "spritesheet.webp"
    atlas.unlink()
    assert "atlas.missing" in issue_codes(validate_pet(pet))
    atlas.write_text("not an image", encoding="utf-8")
    assert "atlas.unreadable" in issue_codes(validate_pet(pet))


def test_manifest_missing_fields_are_reported(tmp_path: Path) -> None:
    pet = tmp_path / "pet"
    pet.mkdir()
    (pet / "pet.json").write_text("{}", encoding="utf-8")
    report = validate_pet(pet)
    codes = issue_codes(report)
    for key in ("id", "displayName", "description", "spriteVersionNumber", "spritesheetPath"):
        assert f"manifest.{key}.type" in codes
    assert "manifest.sprite-version" in codes
    assert "manifest.spritesheet-path" in codes


def test_file_size_gate_uses_configured_limit(
    pet_factory: object, monkeypatch: object
) -> None:
    pet = pet_factory()  # type: ignore[operator]
    monkeypatch.setattr("haru_urara_pet.validation.MAX_ATLAS_BYTES", 1)  # type: ignore[attr-defined]
    report = validate_pet(pet)
    assert "atlas.file-size" in issue_codes(report)
    assert (ATLAS_WIDTH, ATLAS_HEIGHT) == (1536, 2288)
