from __future__ import annotations

import stat
import zipfile
from pathlib import Path

import pytest

from haru_urara_pet.archive import (
    build_pet_archive,
    extracted_pet,
    inspect_archive,
    sha256_file,
)
from haru_urara_pet.validation import validate_pet


def codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}  # type: ignore[attr-defined]


def test_archives_are_byte_reproducible_and_extract_safely(
    pet_factory: object, tmp_path: Path
) -> None:
    pet = pet_factory()  # type: ignore[operator]
    first = build_pet_archive(pet, tmp_path / "first.zip")
    second = build_pet_archive(pet, tmp_path / "second.zip")
    assert first.read_bytes() == second.read_bytes()
    assert sha256_file(first) == sha256_file(second)
    report = inspect_archive(first)
    assert report.ok, report.to_dict()
    assert report.facts["members"] == [
        "SHA256SUMS",
        "haru-urara/pet.json",
        "haru-urara/spritesheet.webp",
    ]
    with extracted_pet(first) as extracted:
        assert validate_pet(extracted).ok


def test_flat_codex_pet_archive(pet_factory: object, tmp_path: Path) -> None:
    pet = pet_factory()  # type: ignore[operator]
    archive = build_pet_archive(pet, tmp_path / "pet.codex-pet")
    report = inspect_archive(archive)
    assert report.ok
    assert report.facts["members"] == ["pet.json", "spritesheet.webp"]


def test_invalid_pet_is_not_packaged(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid pet"):
        build_pet_archive(tmp_path, tmp_path / "bad.zip")


def test_bad_zip_and_missing_archive(tmp_path: Path) -> None:
    missing = inspect_archive(tmp_path / "missing.zip")
    assert "archive.missing" in codes(missing)
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"no")
    assert "archive.unreadable" in codes(inspect_archive(bad))


def test_traversal_duplicate_symlink_and_extras_are_rejected(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    symlink = zipfile.ZipInfo("link")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../pet.json", "{}")
        archive.writestr("../pet.json", "{}")
        archive.writestr("spritesheet.webp", b"data")
        archive.writestr(symlink, "target")
        archive.writestr("extra.txt", "extra")
    report = inspect_archive(archive_path)
    issue_codes = codes(report)
    assert "archive.path" in issue_codes
    assert "archive.duplicate" in issue_codes
    assert "archive.symlink" in issue_codes
    assert "archive.pet-layout" in issue_codes
    assert "archive.extra-members" in issue_codes
    with pytest.raises(ValueError, match="unsafe"), extracted_pet(archive_path):
        pass


def test_archive_size_limits(
    pet_factory: object, tmp_path: Path, monkeypatch: object
) -> None:
    pet = pet_factory()  # type: ignore[operator]
    archive_path = build_pet_archive(pet, tmp_path / "pet.zip")
    monkeypatch.setattr("haru_urara_pet.archive.MAX_ARCHIVE_BYTES", 1)  # type: ignore[attr-defined]
    assert "archive.too-large" in codes(inspect_archive(archive_path))
