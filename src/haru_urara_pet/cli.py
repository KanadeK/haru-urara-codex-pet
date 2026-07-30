"""Command-line interface for the pet and PetSight."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .archive import build_pet_archive, inspect_archive, sha256_file
from .install import (
    bundled_pet_dir,
    doctor,
    install_pet,
    repair_pet,
    restore_pet,
    uninstall_pet,
)
from .petsight import audit_pet, load_policy, render_matrix, write_html_report
from .report import Report
from .validation import validate_pet


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def _source_or_bundled(value: str | None) -> Path:
    return Path(value) if value else bundled_pet_dir()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="urara-pet",
        description="Haru Urara for Codex and PetSight visual accessibility QA.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="strictly validate a v2 pet directory")
    validate.add_argument("path", nargs="?", help="pet directory; defaults to the bundled pet")
    _add_json_flag(validate)

    audit = commands.add_parser(
        "audit",
        help="audit contrast, color-vision scenarios, motion, scale, and baselines",
    )
    audit.add_argument("path", nargs="?", help="pet directory; defaults to the bundled pet")
    audit.add_argument("--policy", help="PetSight JSON policy")
    audit.add_argument("--json-out", help="write the full JSON report")
    audit.add_argument("--matrix-out", help="write a PNG scenario matrix")
    audit.add_argument("--html-out", help="write a self-contained HTML report")
    _add_json_flag(audit)

    matrix = commands.add_parser("matrix", help="render real atlas cells in PetSight scenarios")
    matrix.add_argument("path", nargs="?", help="pet directory; defaults to the bundled pet")
    matrix.add_argument("--policy", help="PetSight JSON policy")
    matrix.add_argument("--output", required=True, help="output PNG")
    _add_json_flag(matrix)

    install = commands.add_parser("install", help="validate, back up, and install atomically")
    install.add_argument("--source", help="pet directory, repository, ZIP, or .codex-pet")
    install.add_argument("--codex-home", help="override the Codex home directory")
    _add_json_flag(install)

    diagnose = commands.add_parser("doctor", help="diagnose installation drift and backups")
    diagnose.add_argument("--source", help="optional expected source for byte comparison")
    diagnose.add_argument("--codex-home", help="override the Codex home directory")
    _add_json_flag(diagnose)

    repair = commands.add_parser("repair", help="reinstall from a verified source with backup")
    repair.add_argument("--source", help="pet directory, repository, ZIP, or .codex-pet")
    repair.add_argument("--codex-home", help="override the Codex home directory")
    _add_json_flag(repair)

    uninstall = commands.add_parser(
        "uninstall", help="move the installed pet into recoverable backups"
    )
    uninstall.add_argument("--codex-home", help="override the Codex home directory")
    _add_json_flag(uninstall)

    restore = commands.add_parser("restore", help="restore a verified backup")
    restore.add_argument("--backup", help="backup directory; defaults to the newest")
    restore.add_argument("--codex-home", help="override the Codex home directory")
    _add_json_flag(restore)

    package = commands.add_parser("package", help="build a byte-reproducible pet archive")
    package.add_argument("path", nargs="?", help="pet directory; defaults to the bundled pet")
    package.add_argument("--output", required=True, help=".zip or .codex-pet output")
    _add_json_flag(package)

    inspect = commands.add_parser("verify-archive", help="inspect a release archive safely")
    inspect.add_argument("path", help="ZIP or .codex-pet archive")
    _add_json_flag(inspect)
    return parser


def _print_report(report: Report, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return
    status = "PASS" if report.ok else "FAIL"
    print(f"{status}: {report.subject}")
    for issue in report.issues:
        location = f" [{issue.location}]" if issue.location else ""
        print(f"{issue.severity.upper()} {issue.code}{location}: {issue.message}")
        if issue.repair:
            print(f"  repair: {issue.repair}")


def _print_payload(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print("PASS" if payload.get("ok") else "FAIL")
    for key, value in payload.items():
        if key != "ok":
            print(f"{key}: {value}")


def _write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return target


def _run(args: argparse.Namespace) -> int:
    command = str(args.command)
    as_json = bool(getattr(args, "json", False))
    if command == "validate":
        report = validate_pet(_source_or_bundled(args.path))
        _print_report(report, as_json)
        return 0 if report.ok else 1
    if command == "audit":
        pet_dir = _source_or_bundled(args.path)
        policy = load_policy(args.policy)
        report = audit_pet(pet_dir, policy=policy)
        matrix: Path | None = None
        if args.matrix_out:
            matrix = render_matrix(pet_dir, args.matrix_out, policy=policy)
        if args.json_out:
            _write_json(args.json_out, report.to_dict())
        if args.html_out:
            matrix_name = (
                Path(matrix).name
                if matrix is not None
                and Path(matrix).parent.resolve() == Path(args.html_out).parent.resolve()
                else str(matrix)
                if matrix is not None
                else None
            )
            write_html_report(report, args.html_out, matrix_name=matrix_name)
        _print_report(report, as_json)
        return 0 if report.ok else 1
    if command == "matrix":
        output = render_matrix(
            _source_or_bundled(args.path),
            args.output,
            policy=load_policy(args.policy),
        )
        payload = {"ok": True, "operation": "matrix", "output": str(output)}
        _print_payload(payload, as_json)
        return 0
    if command == "install":
        payload = install_pet(
            _source_or_bundled(args.source), codex_home=args.codex_home
        )
        _print_payload(payload, as_json)
        return 0
    if command == "doctor":
        report = doctor(source=args.source, codex_home=args.codex_home)
        _print_report(report, as_json)
        return 0 if report.ok else 1
    if command == "repair":
        payload = repair_pet(
            _source_or_bundled(args.source), codex_home=args.codex_home
        )
        _print_payload(payload, as_json)
        return 0
    if command == "uninstall":
        payload = uninstall_pet(codex_home=args.codex_home)
        _print_payload(payload, as_json)
        return 0
    if command == "restore":
        payload = restore_pet(args.backup, codex_home=args.codex_home)
        _print_payload(payload, as_json)
        return 0
    if command == "package":
        target = build_pet_archive(_source_or_bundled(args.path), args.output)
        payload = {
            "ok": True,
            "operation": "package",
            "output": str(target),
            "sha256": sha256_file(target),
        }
        _print_payload(payload, as_json)
        return 0
    if command == "verify-archive":
        report = inspect_archive(args.path)
        _print_report(report, as_json)
        return 0 if report.ok else 1
    raise AssertionError(f"unhandled command: {command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (FileNotFoundError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "ok": False,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        if bool(getattr(args, "json", False)):
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
