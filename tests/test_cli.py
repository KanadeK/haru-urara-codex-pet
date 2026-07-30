from __future__ import annotations

import json
from pathlib import Path

from haru_urara_pet.cli import main


def last_json(capsys: object) -> dict[str, object]:
    return json.loads(capsys.readouterr().out)  # type: ignore[attr-defined,no-any-return]


def test_validate_audit_matrix_package_and_verify(
    pet_factory: object, tmp_path: Path, capsys: object
) -> None:
    pet = pet_factory()  # type: ignore[operator]
    assert main(["validate", str(pet), "--json"]) == 0
    assert last_json(capsys)["ok"] is True

    matrix = tmp_path / "matrix.png"
    report_json = tmp_path / "audit.json"
    report_html = tmp_path / "audit.html"
    policy = tmp_path / "policy.json"
    policy.write_text(
        json.dumps(
            {
                "minimum_edge_contrast": 1.0,
                "warning_edge_contrast": 1.0,
            }
        ),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "audit",
                str(pet),
                "--policy",
                str(policy),
                "--matrix-out",
                str(matrix),
                "--json-out",
                str(report_json),
                "--html-out",
                str(report_html),
                "--json",
            ]
        )
        == 0
    )
    assert last_json(capsys)["ok"] is True
    assert matrix.is_file() and report_json.is_file() and report_html.is_file()

    direct_matrix = tmp_path / "direct.png"
    assert main(["matrix", str(pet), "--output", str(direct_matrix), "--json"]) == 0
    assert last_json(capsys)["operation"] == "matrix"

    archive = tmp_path / "pet.zip"
    assert main(["package", str(pet), "--output", str(archive), "--json"]) == 0
    assert last_json(capsys)["sha256"]
    assert main(["verify-archive", str(archive), "--json"]) == 0
    assert last_json(capsys)["ok"] is True


def test_install_doctor_repair_uninstall_restore_commands(
    pet_factory: object, tmp_path: Path, capsys: object
) -> None:
    pet = pet_factory()  # type: ignore[operator]
    home = tmp_path / "codex"
    common = ["--source", str(pet), "--codex-home", str(home), "--json"]
    assert main(["install", *common]) == 0
    assert last_json(capsys)["operation"] == "install"
    assert main(["doctor", *common]) == 0
    assert last_json(capsys)["ok"] is True
    assert main(["repair", *common]) == 0
    assert last_json(capsys)["operation"] == "repair"
    assert main(["uninstall", "--codex-home", str(home), "--json"]) == 0
    assert last_json(capsys)["changed"] is True
    assert main(["restore", "--codex-home", str(home), "--json"]) == 0
    assert last_json(capsys)["operation"] == "restore"


def test_cli_failure_json_and_human_output(tmp_path: Path, capsys: object) -> None:
    assert main(["validate", str(tmp_path), "--json"]) == 1
    assert last_json(capsys)["ok"] is False
    assert main(["install", "--source", str(tmp_path), "--json"]) == 2
    payload = last_json(capsys)
    assert payload["ok"] is False
    assert payload["error"]["type"] == "FileNotFoundError"  # type: ignore[index]

    assert main(["validate", str(tmp_path)]) == 1
    assert "FAIL:" in capsys.readouterr().out  # type: ignore[attr-defined]
    assert main(["install", "--source", str(tmp_path)]) == 2
    assert "ERROR FileNotFoundError" in capsys.readouterr().err  # type: ignore[attr-defined]
