from __future__ import annotations

import json
from pathlib import Path

import pytest

from haru_urara_pet.petsight import (
    PetSightPolicy,
    audit_pet,
    load_policy,
    render_matrix,
    write_html_report,
)


def codes(report: object) -> set[str]:
    return {issue.code for issue in report.issues}  # type: ignore[attr-defined]


def test_real_pixel_audit_and_matrix_pass(pet_factory: object, tmp_path: Path) -> None:
    pet = pet_factory()  # type: ignore[operator]
    policy = PetSightPolicy(minimum_edge_contrast=1.0, warning_edge_contrast=1.0)
    report = audit_pet(pet, policy=policy)
    assert report.ok, report.to_dict()
    assert len(report.facts["petsight"]["frames"]) == 74
    assert report.facts["petsight"]["neutral_look_frame"] == {
        "row": 0,
        "column": 6,
    }
    assert set(report.facts["petsight"]["modes"]) == {
        "normal",
        "protanopia",
        "deuteranopia",
        "tritanopia",
    }
    matrix = render_matrix(pet, tmp_path / "matrix.png", policy=policy)
    assert matrix.is_file()
    assert matrix.stat().st_size > 1000
    html = write_html_report(report, tmp_path / "report.html", matrix.name)
    content = html.read_text(encoding="utf-8")
    assert "PetSight report: PASS" in content
    assert "matrix.png" in content


def test_low_contrast_and_inert_rows_fail(pet_factory: object) -> None:
    pet = pet_factory(
        outline=(120, 120, 120), fill=(120, 120, 120), animate=False
    )  # type: ignore[operator]
    policy = PetSightPolicy(
        backgrounds={"same-gray": (120, 120, 120)},
        minimum_edge_contrast=1.2,
        warning_edge_contrast=1.3,
    )
    report = audit_pet(pet, policy=policy)
    assert "petsight.contrast.edge" in codes(report)
    assert "petsight.animation.duplicate" in codes(report)
    assert "petsight.animation.inert" in codes(report)


def test_warning_thresholds_are_reported(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    report = audit_pet(
        pet,
        policy=PetSightPolicy(
            minimum_edge_contrast=1.0,
            warning_edge_contrast=20.0,
            warning_area_cv=0.0,
            maximum_area_cv=2.0,
            warning_baseline_span=0,
            maximum_baseline_span=999,
        ),
    )
    issue_codes = codes(report)
    assert "petsight.contrast.edge-warning" in issue_codes
    assert "petsight.animation.size-variation" in issue_codes
    assert "petsight.animation.baseline-variation" in issue_codes
    assert report.ok


def test_invalid_pet_stops_before_pixel_audit(tmp_path: Path) -> None:
    report = audit_pet(tmp_path)
    assert not report.ok
    assert "validation.manifest.missing" in codes(report)
    with pytest.raises(ValueError, match="invalid pet"):
        render_matrix(tmp_path, tmp_path / "matrix.png")


def test_policy_loading_and_validation(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "backgrounds": {"night": "#010203"},
                "minimum_edge_contrast": 1.1,
                "warning_edge_contrast": 1.4,
                "display_scale": 0.75,
            }
        ),
        encoding="utf-8",
    )
    policy = load_policy(policy_path)
    assert policy.backgrounds == {"night": (1, 2, 3)}
    assert policy.display_scale == 0.75
    for payload, expected in (
        ([], "JSON object"),
        ({"unknown": 1}, "unknown PetSight"),
        ({"backgrounds": {}}, "non-empty"),
        ({"backgrounds": {"bad": "nope"}}, "invalid color"),
        ({"display_scale": 9}, "display_scale"),
        (
            {"minimum_edge_contrast": 2, "warning_edge_contrast": 1},
            "edge thresholds",
        ),
    ):
        policy_path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match=expected):
            load_policy(policy_path)


def test_coverage_and_motion_policy_can_flag_fixture(pet_factory: object) -> None:
    pet = pet_factory()  # type: ignore[operator]
    report = audit_pet(
        pet,
        policy=PetSightPolicy(
            minimum_edge_contrast=1.0,
            warning_edge_contrast=1.0,
            minimum_coverage=0.9,
            maximum_coverage=0.95,
            minimum_motion_ratio=0.9,
        ),
    )
    assert "petsight.coverage.too-small" in codes(report)
    assert "petsight.animation.inert" in codes(report)
