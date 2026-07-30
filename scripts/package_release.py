"""Build and verify all v0.1 release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from haru_urara_pet import __version__  # noqa: E402
from haru_urara_pet.archive import (  # noqa: E402
    build_pet_archive,
    inspect_archive,
    sha256_file,
)
from haru_urara_pet.petsight import (  # noqa: E402
    audit_pet,
    load_policy,
    render_matrix,
    write_html_report,
)
from haru_urara_pet.spec import REQUIRED_CELL_COUNT, UNUSED_CELL_COUNT  # noqa: E402
from haru_urara_pet.validation import validate_pet  # noqa: E402

PET_DIR = ROOT / "pet" / "haru-urara"
POLICY = ROOT / "examples" / "petsight-policy.json"


def _zip_fingerprint(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        return [
            {
                "name": info.filename,
                "date_time": list(info.date_time),
                "compress_type": info.compress_type,
                "external_attr": info.external_attr,
                "file_size": info.file_size,
                "compressed_size": info.compress_size,
                "crc": info.CRC,
                "sha256": hashlib.sha256(archive.read(info)).hexdigest(),
            }
            for info in archive.infolist()
        ]


def _build_pet_pair(stage: Path, suffix: str) -> tuple[Path, Path]:
    flat = build_pet_archive(PET_DIR, stage / f"haru-urara-{suffix}.codex-pet")
    folder = build_pet_archive(
        PET_DIR,
        stage / f"haru-urara-codex-pet-v{__version__}-{suffix}.zip",
    )
    return flat, folder


def _assert_deterministic(stage: Path) -> tuple[Path, Path, dict[str, Any]]:
    first_flat, first_folder = _build_pet_pair(stage, "first")
    time.sleep(1.1)
    second_flat, second_folder = _build_pet_pair(stage, "second")
    comparisons: dict[str, Any] = {}
    for kind, first, second in (
        ("codex_pet", first_flat, second_flat),
        ("folder_zip", first_folder, second_folder),
    ):
        same_bytes = first.read_bytes() == second.read_bytes()
        same_metadata = _zip_fingerprint(first) == _zip_fingerprint(second)
        comparisons[kind] = {
            "byte_identical": same_bytes,
            "metadata_identical": same_metadata,
            "sha256": sha256_file(first),
            "members": _zip_fingerprint(first),
        }
        if not same_bytes or not same_metadata:
            raise RuntimeError(f"{kind} is not deterministic across delayed builds")
    final_flat = stage / "haru-urara.codex-pet"
    final_folder = stage / f"haru-urara-codex-pet-v{__version__}.zip"
    first_flat.replace(final_flat)
    first_folder.replace(final_folder)
    second_flat.unlink()
    second_folder.unlink()
    return final_flat, final_folder, comparisons


def _run_build(stage: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(stage),
            str(ROOT),
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"python package build failed with exit code {result.returncode}")


def build_release(output_dir: Path) -> list[Path]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"release output is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    validation = validate_pet(PET_DIR)
    if not validation.ok:
        raise ValueError(f"pet validation failed: {validation.to_dict()}")
    policy = load_policy(POLICY)
    audit = audit_pet(PET_DIR, policy=policy)
    if not audit.ok:
        raise ValueError(f"PetSight failed: {audit.to_dict()}")

    with tempfile.TemporaryDirectory(prefix=".urara-release-", dir=output_dir.parent) as raw:
        stage = Path(raw)
        flat, folder, comparisons = _assert_deterministic(stage)
        if not inspect_archive(flat).ok or not inspect_archive(folder).ok:
            raise ValueError("a generated pet archive failed safe inspection")

        report_json = stage / "petsight-report.json"
        report_json.write_text(
            json.dumps(audit.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        matrix = render_matrix(PET_DIR, stage / "petsight-matrix.png", policy=policy)
        write_html_report(audit, stage / "petsight-report.html", matrix.name)
        _run_build(stage)

        manifest_path = stage / "release-manifest.json"
        provisional = sorted(
            path for path in stage.iterdir() if path.is_file() and path != manifest_path
        )
        manifest_path.write_text(
            json.dumps(
                {
                    "project": "haru-urara-codex-pet",
                    "version": __version__,
                    "sprite_version_number": 2,
                    "required_cells": REQUIRED_CELL_COUNT,
                    "unused_cells": UNUSED_CELL_COUNT,
                    "pet_archives": comparisons,
                    "artifacts": {
                        path.name: {
                            "bytes": path.stat().st_size,
                            "sha256": sha256_file(path),
                        }
                        for path in provisional
                    },
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        artifacts = sorted(path for path in stage.iterdir() if path.is_file())
        sums = stage / "SHA256SUMS"
        sums.write_text(
            "".join(f"{sha256_file(path)}  {path.name}\n" for path in artifacts),
            encoding="utf-8",
            newline="\n",
        )
        artifacts.append(sums)
        delivered: list[Path] = []
        for source in artifacts:
            target = output_dir / source.name
            shutil.copy2(source, target)
            delivered.append(target)
    return sorted(delivered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args(argv)
    try:
        artifacts = build_release(args.output_dir.resolve())
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"RELEASE BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    print("Release build passed:")
    for artifact in artifacts:
        print(f"  {artifact.name}  {artifact.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
