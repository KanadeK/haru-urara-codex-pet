"""Deterministic, traversal-safe Codex pet archives."""

from __future__ import annotations

import hashlib
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from .report import Report
from .validation import validate_pet

PET_FILENAMES = ("pet.json", "spritesheet.webp")
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
MAX_MEMBER_BYTES = 13 * 1024 * 1024
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    return info


def build_pet_archive(
    pet_dir: str | Path,
    output: str | Path,
    *,
    flat: bool | None = None,
) -> Path:
    root = Path(pet_dir)
    validation = validate_pet(root)
    if not validation.ok:
        raise ValueError("refusing to package an invalid pet")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    use_flat = target.suffix == ".codex-pet" if flat is None else flat
    prefix = "" if use_flat else f"{root.name}/"
    entries = [(prefix + name, root / name) for name in PET_FILENAMES]
    checksums = "".join(f"{sha256_file(path)}  {name}\n" for name, path in entries).encode()
    with zipfile.ZipFile(target, "w", allowZip64=False) as archive:
        for name, path in sorted(entries):
            archive.writestr(_zip_info(name), path.read_bytes(), compresslevel=9)
        if not use_flat:
            archive.writestr(_zip_info("SHA256SUMS"), checksums, compresslevel=9)
    return target


def inspect_archive(path: str | Path) -> Report:
    archive_path = Path(path)
    report = Report(subject=str(archive_path))
    try:
        archive_size = archive_path.stat().st_size
    except OSError as exc:
        report.add("error", "archive.missing", str(exc), archive_path)
        return report
    if archive_size > MAX_ARCHIVE_BYTES:
        report.add(
            "error",
            "archive.too-large",
            f"Archive is {archive_size} bytes; limit is {MAX_ARCHIVE_BYTES}.",
            archive_path,
        )
        return report
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as exc:
        report.add("error", "archive.unreadable", str(exc), archive_path)
        return report

    with archive:
        seen: set[str] = set()
        members: list[str] = []
        total = 0
        for info in archive.infolist():
            normalized = info.filename.replace("\\", "/")
            candidate = PurePosixPath(normalized)
            members.append(normalized)
            if normalized in seen:
                report.add(
                    "error",
                    "archive.duplicate",
                    f"Duplicate member: {normalized}",
                    archive_path,
                )
            seen.add(normalized)
            if (
                candidate.is_absolute()
                or ".." in candidate.parts
                or not candidate.parts
                or ":" in candidate.parts[0]
            ):
                report.add(
                    "error",
                    "archive.path",
                    f"Unsafe member path: {normalized}",
                    archive_path,
                )
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                report.add(
                    "error",
                    "archive.symlink",
                    f"Symbolic links are forbidden: {normalized}",
                    archive_path,
                )
            if info.file_size > MAX_MEMBER_BYTES:
                report.add(
                    "error",
                    "archive.member-too-large",
                    f"{normalized} is {info.file_size} bytes.",
                    archive_path,
                )
            total += info.file_size
        if total > MAX_ARCHIVE_BYTES:
            report.add(
                "error",
                "archive.expanded-too-large",
                f"Expanded members total {total} bytes.",
                archive_path,
            )

        pet_candidates = [
            name for name in members if PurePosixPath(name).name == "pet.json"
        ]
        sprite_candidates = [
            name for name in members if PurePosixPath(name).name == "spritesheet.webp"
        ]
        if len(pet_candidates) != 1 or len(sprite_candidates) != 1:
            report.add(
                "error",
                "archive.pet-layout",
                "Archive must contain exactly one pet.json and one spritesheet.webp.",
                archive_path,
            )
        elif PurePosixPath(pet_candidates[0]).parent != PurePosixPath(
            sprite_candidates[0]
        ).parent:
            report.add(
                "error",
                "archive.pet-layout",
                "pet.json and spritesheet.webp must share one directory.",
                archive_path,
            )
        allowed = set(pet_candidates + sprite_candidates + ["SHA256SUMS"])
        extras = sorted(set(members) - allowed)
        if extras:
            report.add(
                "error",
                "archive.extra-members",
                f"Unexpected archive members: {', '.join(extras)}.",
                archive_path,
            )
        report.facts.update(
            {
                "archive_bytes": archive_size,
                "expanded_bytes": total,
                "members": sorted(members),
            }
        )
    return report


@contextmanager
def extracted_pet(path: str | Path) -> Iterator[Path]:
    archive_path = Path(path)
    inspection = inspect_archive(archive_path)
    if not inspection.ok:
        raise ValueError("unsafe or invalid pet archive")
    with tempfile.TemporaryDirectory(prefix="urara-pet-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            pet_member = next(
                info
                for info in archive.infolist()
                if PurePosixPath(info.filename).name == "pet.json"
            )
            sprite_member = next(
                info
                for info in archive.infolist()
                if PurePosixPath(info.filename).name == "spritesheet.webp"
            )
            for info in (pet_member, sprite_member):
                destination = root / PurePosixPath(info.filename).name
                with archive.open(info) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
        yield root
