from __future__ import annotations

import json
from pathlib import Path

import pytest

from haru_urara_pet.archive import build_pet_archive
from haru_urara_pet.install import (
    doctor,
    install_pet,
    list_backups,
    restore_pet,
    uninstall_pet,
)


def codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}  # type: ignore[attr-defined]


def test_install_diagnose_reinstall_uninstall_restore(
    pet_factory: object, tmp_path: Path
) -> None:
    source = pet_factory()  # type: ignore[operator]
    home = tmp_path / "codex"
    first = install_pet(source, codex_home=home)
    assert first["ok"] and first["backup"] is None
    target = home / "pets" / "haru-urara"
    assert target.is_dir()
    assert doctor(source=source, codex_home=home).ok

    manifest = json.loads((target / "pet.json").read_text(encoding="utf-8"))
    manifest["description"] = "drift"
    (target / "pet.json").write_text(json.dumps(manifest), encoding="utf-8")
    drift = doctor(source=source, codex_home=home)
    assert "install.drift" in codes(drift)

    repaired = install_pet(source, codex_home=home)
    assert Path(repaired["backup"]).is_dir()
    assert doctor(source=source, codex_home=home).ok

    removed = uninstall_pet(codex_home=home)
    assert removed["changed"] is True
    assert not target.exists()
    missing = doctor(codex_home=home)
    assert "install.missing" in codes(missing)
    assert list_backups(codex_home=home)

    restored = restore_pet(codex_home=home)
    assert restored["operation"] == "restore"
    assert target.is_dir()
    assert uninstall_pet(codex_home=home)["changed"] is True
    assert uninstall_pet(codex_home=home)["changed"] is False


def test_install_from_archive_and_explicit_backup(
    pet_factory: object, tmp_path: Path
) -> None:
    source = pet_factory()  # type: ignore[operator]
    archive = build_pet_archive(source, tmp_path / "pet.codex-pet")
    home = tmp_path / "codex"
    install_pet(archive, codex_home=home)
    uninstall_pet(codex_home=home)
    backup = list_backups(codex_home=home)[0]
    restored = restore_pet(backup, codex_home=home)
    assert restored["restored_from"] == str(backup)


def test_restore_and_source_failures(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no verified"):
        restore_pet(codex_home=tmp_path)
    with pytest.raises(FileNotFoundError, match="no pet.json"):
        install_pet(tmp_path / "unknown", codex_home=tmp_path / "codex")


def test_invalid_install_and_invalid_uninstall_are_blocked(
    pet_factory: object, tmp_path: Path
) -> None:
    source = pet_factory()  # type: ignore[operator]
    (source / "pet.json").unlink()
    with pytest.raises(ValueError, match="failed validation"):
        install_pet(source, codex_home=tmp_path / "codex")

    valid = pet_factory()  # type: ignore[operator]
    home = tmp_path / "codex2"
    install_pet(valid, codex_home=home)
    (home / "pets" / "haru-urara" / "pet.json").unlink()
    with pytest.raises(ValueError, match="invalid"):
        uninstall_pet(codex_home=home)
