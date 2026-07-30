"""Run the complete local acceptance and release-readiness gate."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from haru_urara_pet import __version__  # noqa: E402
from haru_urara_pet.archive import inspect_archive, sha256_file  # noqa: E402
from haru_urara_pet.spec import REQUIRED_CELL_COUNT, UNUSED_CELL_COUNT  # noqa: E402


def run(*arguments: str) -> None:
    print(f"\n> {' '.join(arguments)}", flush=True)
    result = subprocess.run(arguments, cwd=ROOT, check=False)
    if result.returncode:
        raise RuntimeError(
            f"command failed with exit code {result.returncode}: {' '.join(arguments)}"
        )


def verify_version_metadata() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project_version = tomllib.load(stream)["project"]["version"]
    if project_version != __version__:
        raise RuntimeError(
            f"version mismatch: pyproject={project_version}, runtime={__version__}"
        )
    print(f"Version metadata agrees: {__version__}.")


def check_markdown_links() -> None:
    pattern = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
    failures: list[str] = []
    files = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").glob("*.md"))
    for document in files:
        text = document.read_text(encoding="utf-8")
        for raw_target in pattern.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if (
                not target
                or target.startswith(("http://", "https://", "mailto:", "#"))
            ):
                continue
            path_text = target.split("#", 1)[0]
            if not path_text:
                continue
            destination = (document.parent / path_text).resolve()
            if not destination.exists():
                failures.append(f"{document.relative_to(ROOT)} -> {target}")
    if failures:
        raise RuntimeError("broken local Markdown links:\n" + "\n".join(failures))
    print(f"Markdown link check passed ({len(files)} documents).")


def verify_checksums(release_dir: Path) -> None:
    lines = (release_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    expected: set[str] = set()
    for line in lines:
        digest, name = line.split("  ", 1)
        artifact = release_dir / name
        if not artifact.is_file():
            raise RuntimeError(f"checksum references missing artifact: {name}")
        if sha256_file(artifact) != digest:
            raise RuntimeError(f"checksum mismatch: {name}")
        expected.add(name)
    actual = {path.name for path in release_dir.iterdir() if path.name != "SHA256SUMS"}
    if expected != actual:
        raise RuntimeError(
            f"checksum coverage differs: missing={actual - expected}, extra={expected - actual}"
        )
    print(f"Checksum verification passed ({len(expected)} artifacts).")


def verify_python_packages(release_dir: Path) -> None:
    wheel = next(release_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required = {
            "haru_urara_pet/bundled_pet/pet.json",
            "haru_urara_pet/bundled_pet/spritesheet.webp",
        }
        if not required <= names:
            raise RuntimeError(f"wheel is missing bundled pet files: {required - names}")
    sdist = next(release_dir.glob("*.tar.gz"))
    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
        if not any(name.endswith("/pet/haru-urara/pet.json") for name in names):
            raise RuntimeError("sdist is missing pet.json")
        if not any(name.endswith("/pet/haru-urara/spritesheet.webp") for name in names):
            raise RuntimeError("sdist is missing spritesheet.webp")
    print("Wheel and sdist contain the verified pet.")


def verify_release_archives(release_dir: Path) -> None:
    for archive in (
        release_dir / "haru-urara.codex-pet",
        next(release_dir.glob("haru-urara-codex-pet-v*.zip")),
    ):
        report = inspect_archive(archive)
        if not report.ok:
            raise RuntimeError(f"unsafe release archive: {report.to_dict()}")
        with zipfile.ZipFile(archive) as opened:
            for info in opened.infolist():
                if info.date_time != (2026, 1, 1, 0, 0, 0):
                    raise RuntimeError(
                        f"nondeterministic ZIP timestamp in {archive.name}: {info.filename}"
                    )
    manifest = release_dir / "release-manifest.json"
    if not manifest.is_file():
        raise RuntimeError("release manifest is missing")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("required_cells") != REQUIRED_CELL_COUNT:
        raise RuntimeError("release manifest has the wrong required-cell count")
    if payload.get("unused_cells") != UNUSED_CELL_COUNT:
        raise RuntimeError("release manifest has the wrong unused-cell count")
    print("Release archive safety and metadata checks passed.")


def main() -> int:
    try:
        verify_version_metadata()
        run(sys.executable, "-m", "compileall", "-q", "src", "scripts", "tests")
        run(sys.executable, "-m", "ruff", "check", ".")
        run(sys.executable, "-m", "mypy", "src")
        with tempfile.TemporaryDirectory(prefix="urara-acceptance-") as raw:
            temporary = Path(raw)
            run(
                sys.executable,
                "-m",
                "pytest",
                "--cov=haru_urara_pet",
                "--cov-branch",
                "--cov-report=term-missing",
                f"--cov-report=xml:{temporary / 'coverage.xml'}",
            )
            run(sys.executable, "scripts/secret_scan.py")
            check_markdown_links()
            release_dir = temporary / "release"
            run(
                sys.executable,
                "scripts/package_release.py",
                "--output-dir",
                str(release_dir),
            )
            verify_checksums(release_dir)
            verify_python_packages(release_dir)
            verify_release_archives(release_dir)
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"\nACCEPTANCE FAILED: {exc}", file=sys.stderr)
        return 1
    print("\nACCEPTANCE PASSED: code, pet, recovery paths, and release artifacts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
