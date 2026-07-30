"""Recoverable, validate-before-write installation."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .archive import PET_FILENAMES, extracted_pet, sha256_file
from .report import Report
from .validation import validate_pet

PET_ID = "haru-urara"


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def bundled_pet_dir() -> Path:
    candidates = (
        Path(__file__).resolve().parent / "bundled_pet",
        Path(__file__).resolve().parents[2] / "pet" / PET_ID,
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "bundled pet files are unavailable; pass --source to an unpacked pet or release archive"
    )


@contextmanager
def _pet_source(path: str | Path) -> Iterator[Path]:
    source = Path(path)
    if source.is_file():
        with extracted_pet(source) as extracted:
            yield extracted
        return
    if (source / "pet.json").is_file():
        yield source
        return
    if source.is_dir() and any((source / name).exists() for name in PET_FILENAMES):
        # A partial pet is still a pet source. Let validate_pet report the
        # precise missing/corrupt file instead of disguising it as a lookup failure.
        yield source
        return
    nested = source / "pet" / PET_ID
    if (nested / "pet.json").is_file():
        yield nested
        return
    raise FileNotFoundError(f"no pet.json found under {source}")


@contextmanager
def _install_lock(pets_root: Path, timeout: float = 5.0) -> Iterator[Path]:
    pets_root.mkdir(parents=True, exist_ok=True)
    lock = pets_root / f".{PET_ID}.install.lock"
    deadline = time.monotonic() + timeout
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"another installation holds {lock}") from None
            time.sleep(0.05)
    try:
        payload = json.dumps({"pid": os.getpid(), "created_at": time.time()}).encode()
        os.write(descriptor, payload)
        os.close(descriptor)
        descriptor = None
        yield lock
    finally:
        if descriptor is not None:
            os.close(descriptor)
        lock.unlink(missing_ok=True)


def _tree_hash(pet_dir: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for name in PET_FILENAMES:
        digest.update(name.encode())
        digest.update(bytes.fromhex(sha256_file(pet_dir / name)))
    return digest.hexdigest()


def _backup_path(pets_root: Path, source: Path) -> Path:
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return pets_root / ".backups" / PET_ID / f"{timestamp}-{_tree_hash(source)[:12]}"


def _copy_pet(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for name in PET_FILENAMES:
        shutil.copy2(source / name, destination / name)


def install_pet(
    source: str | Path,
    *,
    codex_home: str | Path | None = None,
) -> dict[str, Any]:
    home = Path(codex_home) if codex_home is not None else default_codex_home()
    pets_root = home / "pets"
    target = pets_root / PET_ID
    with _pet_source(source) as pet_source:
        validation = validate_pet(pet_source)
        if not validation.ok:
            raise ValueError("source pet failed validation")
        with _install_lock(pets_root):
            stage = pets_root / f".{PET_ID}.staging-{uuid.uuid4().hex}"
            displaced = pets_root / f".{PET_ID}.previous-{uuid.uuid4().hex}"
            backup: Path | None = None
            try:
                _copy_pet(pet_source, stage)
                staged_validation = validate_pet(stage)
                if not staged_validation.ok:
                    raise ValueError("staged pet failed validation")
                if target.exists():
                    backup = _backup_path(pets_root, target)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(target, backup)
                    target.replace(displaced)
                stage.replace(target)
                installed_validation = validate_pet(target)
                if not installed_validation.ok:
                    raise ValueError("installed pet failed validation")
                if displaced.exists():
                    shutil.rmtree(displaced)
            except Exception:
                if stage.exists():
                    shutil.rmtree(stage)
                if target.exists() and not validate_pet(target).ok:
                    shutil.rmtree(target)
                if displaced.exists() and not target.exists():
                    displaced.replace(target)
                raise
    return {
        "ok": True,
        "operation": "install",
        "target": str(target),
        "backup": str(backup) if backup else None,
        "sha256": _tree_hash(target),
    }


def uninstall_pet(*, codex_home: str | Path | None = None) -> dict[str, Any]:
    home = Path(codex_home) if codex_home is not None else default_codex_home()
    pets_root = home / "pets"
    target = pets_root / PET_ID
    with _install_lock(pets_root):
        if not target.exists():
            return {"ok": True, "operation": "uninstall", "changed": False, "target": str(target)}
        validation = validate_pet(target)
        if not validation.ok:
            raise ValueError("installed pet is invalid; use doctor before removing it")
        backup = _backup_path(pets_root, target)
        backup.parent.mkdir(parents=True, exist_ok=True)
        target.replace(backup)
    return {
        "ok": True,
        "operation": "uninstall",
        "changed": True,
        "target": str(target),
        "backup": str(backup),
    }


def list_backups(*, codex_home: str | Path | None = None) -> list[Path]:
    home = Path(codex_home) if codex_home is not None else default_codex_home()
    backup_root = home / "pets" / ".backups" / PET_ID
    if not backup_root.exists():
        return []
    return sorted(
        (entry for entry in backup_root.iterdir() if entry.is_dir()),
        key=lambda entry: entry.name,
        reverse=True,
    )


def restore_pet(
    backup: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
) -> dict[str, Any]:
    candidates = list_backups(codex_home=codex_home)
    source = Path(backup) if backup is not None else (candidates[0] if candidates else None)
    if source is None:
        raise FileNotFoundError("no verified Haru Urara backup is available")
    validation = validate_pet(source)
    if not validation.ok:
        raise ValueError(f"backup failed validation: {source}")
    result = install_pet(source, codex_home=codex_home)
    result["operation"] = "restore"
    result["restored_from"] = str(source)
    return result


def doctor(
    *,
    source: str | Path | None = None,
    codex_home: str | Path | None = None,
) -> Report:
    home = Path(codex_home) if codex_home is not None else default_codex_home()
    target = home / "pets" / PET_ID
    report = Report(subject=str(target))
    if not target.exists():
        report.add(
            "error",
            "install.missing",
            "Haru Urara is not installed.",
            target,
            "Run urara-pet install.",
        )
        report.facts["backups"] = [str(path) for path in list_backups(codex_home=home)]
        return report
    installed = validate_pet(target)
    report.merge(installed, "installed")
    if installed.ok:
        report.facts["installed_hash"] = _tree_hash(target)
    if source is not None:
        with _pet_source(source) as source_dir:
            expected = validate_pet(source_dir)
            report.merge(expected, "source")
            if expected.ok and installed.ok:
                expected_hash = _tree_hash(source_dir)
                installed_hash = _tree_hash(target)
                report.facts["source_hash"] = expected_hash
                if expected_hash != installed_hash:
                    report.add(
                        "error",
                        "install.drift",
                        "Installed pet bytes differ from the selected source.",
                        target,
                        "Run urara-pet repair with the same --source.",
                    )
    report.facts["backups"] = [str(path) for path in list_backups(codex_home=home)]
    return report


def repair_pet(
    source: str | Path,
    *,
    codex_home: str | Path | None = None,
) -> dict[str, Any]:
    result = install_pet(source, codex_home=codex_home)
    result["operation"] = "repair"
    return result


def isolated_codex_home() -> Path:
    """Create a disposable Codex home for manual demonstrations."""

    return Path(tempfile.mkdtemp(prefix="urara-codex-home-"))
