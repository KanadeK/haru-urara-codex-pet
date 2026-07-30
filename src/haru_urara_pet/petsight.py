"""PetSight: perceptual QA for tiny animated Codex pets."""

from __future__ import annotations

import html
import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .report import Report
from .spec import (
    ANIMATION_ROWS,
    CELL_HEIGHT,
    CELL_WIDTH,
    NEUTRAL_LOOK_FRAME,
    cell_box,
)
from .validation import validate_pet

RGB = tuple[int, int, int]

_CVD_MATRICES: dict[str, tuple[float, ...]] = {
    "normal": (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ),
    "protanopia": (
        0.56667,
        0.43333,
        0.0,
        0.55833,
        0.44167,
        0.0,
        0.0,
        0.24167,
        0.75833,
    ),
    "deuteranopia": (
        0.625,
        0.375,
        0.0,
        0.70,
        0.30,
        0.0,
        0.0,
        0.30,
        0.70,
    ),
    "tritanopia": (
        0.95,
        0.05,
        0.0,
        0.0,
        0.43333,
        0.56667,
        0.0,
        0.475,
        0.525,
    ),
}


@dataclass(frozen=True, slots=True)
class PetSightPolicy:
    backgrounds: dict[str, RGB] = field(
        default_factory=lambda: {
            "codex-dark": (13, 17, 23),
            "paper-light": (255, 255, 255),
        }
    )
    minimum_edge_contrast: float = 1.12
    warning_edge_contrast: float = 1.35
    minimum_motion_ratio: float = 0.002
    maximum_area_cv: float = 0.36
    warning_area_cv: float = 0.22
    maximum_baseline_span: int = 18
    warning_baseline_span: int = 10
    minimum_coverage: float = 0.015
    maximum_coverage: float = 0.82
    display_scale: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["backgrounds"] = {
            name: _format_hex(color) for name, color in self.backgrounds.items()
        }
        return result


@dataclass(frozen=True, slots=True)
class FrameMetrics:
    row: str
    column: int
    visible_pixels: int
    coverage: float
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]
    baseline: int
    edge_contrast_p10: float
    worst_scenario: str


def _parse_hex_color(value: object) -> RGB:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"invalid color {value!r}; expected #RRGGBB")
    try:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"invalid color {value!r}; expected #RRGGBB") from exc


def _format_hex(color: RGB) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in color)


def load_policy(path: str | Path | None = None) -> PetSightPolicy:
    if path is None:
        return PetSightPolicy()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("PetSight policy must be a JSON object")
    allowed = set(PetSightPolicy.__dataclass_fields__)
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ValueError(f"unknown PetSight policy keys: {', '.join(unknown)}")
    values = dict(raw)
    backgrounds = values.get("backgrounds")
    if backgrounds is not None:
        if not isinstance(backgrounds, dict) or not backgrounds:
            raise ValueError("backgrounds must be a non-empty JSON object")
        values["backgrounds"] = {
            str(name): _parse_hex_color(color) for name, color in backgrounds.items()
        }
    policy = PetSightPolicy(**values)
    if not 0.1 <= policy.display_scale <= 2.0:
        raise ValueError("display_scale must be between 0.1 and 2.0")
    if not 1.0 <= policy.minimum_edge_contrast <= policy.warning_edge_contrast:
        raise ValueError(
            "edge thresholds must satisfy 1 <= minimum_edge_contrast <= "
            "warning_edge_contrast"
        )
    return policy


def _srgb_channel_to_linear(channel: int) -> float:
    value = channel / 255.0
    if value <= 0.04045:
        return value / 12.92
    return float(((value + 0.055) / 1.055) ** 2.4)


def _luminance(color: RGB) -> float:
    red, green, blue = (_srgb_channel_to_linear(channel) for channel in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: RGB, second: RGB) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _transform(color: RGB, matrix: tuple[float, ...]) -> RGB:
    red, green, blue = color
    transformed = (
        matrix[0] * red + matrix[1] * green + matrix[2] * blue,
        matrix[3] * red + matrix[4] * green + matrix[5] * blue,
        matrix[6] * red + matrix[7] * green + matrix[8] * blue,
    )
    return tuple(max(0, min(255, round(channel))) for channel in transformed)  # type: ignore[return-value]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 1.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _mask(cell: Image.Image) -> Image.Image:
    return cell.getchannel("A").point(lambda alpha: 255 if alpha > 16 else 0)


def _edge_colors(cell: Image.Image, mask: Image.Image) -> list[RGB]:
    eroded = mask.filter(ImageFilter.MinFilter(3))
    inside_edge = ImageChops.subtract(mask, eroded)
    rgba = cell.convert("RGBA")
    rgba_pixels = cast(
        tuple[tuple[int, int, int, int], ...],
        rgba.get_flattened_data(),
    )
    edge_pixels = cast(tuple[int, ...], inside_edge.get_flattened_data())
    return [
        (red, green, blue)
        for (red, green, blue, _alpha), edge in zip(
            rgba_pixels,
            edge_pixels,
            strict=True,
        )
        if edge
    ]


def _frame_metrics(
    cell: Image.Image,
    row_name: str,
    column: int,
    policy: PetSightPolicy,
) -> FrameMetrics:
    mask = _mask(cell)
    bbox = mask.getbbox()
    if bbox is None:
        return FrameMetrics(row_name, column, 0, 0.0, (0, 0, 0, 0), (0.0, 0.0), 0, 1.0, "")
    pixels = cast(tuple[int, ...], mask.get_flattened_data())
    visible = sum(value > 0 for value in pixels)
    coordinates = [
        (index % CELL_WIDTH, index // CELL_WIDTH)
        for index, value in enumerate(pixels)
        if value
    ]
    centroid_x = statistics.fmean(point[0] for point in coordinates)
    centroid_y = statistics.fmean(point[1] for point in coordinates)
    baseline = max(point[1] for point in coordinates)
    edge_colors = _edge_colors(cell, mask)
    scenarios: dict[str, float] = {}
    for mode, matrix in _CVD_MATRICES.items():
        transformed_edges = [_transform(color, matrix) for color in edge_colors]
        for background_name, background in policy.backgrounds.items():
            transformed_background = _transform(background, matrix)
            ratios = [_contrast(color, transformed_background) for color in transformed_edges]
            scenarios[f"{mode}/{background_name}"] = _percentile(ratios, 0.10)
    worst_scenario, worst_ratio = min(scenarios.items(), key=lambda item: item[1])
    return FrameMetrics(
        row=row_name,
        column=column,
        visible_pixels=visible,
        coverage=visible / (CELL_WIDTH * CELL_HEIGHT),
        bbox=bbox,
        centroid=(round(centroid_x, 3), round(centroid_y, 3)),
        baseline=baseline,
        edge_contrast_p10=round(worst_ratio, 4),
        worst_scenario=worst_scenario,
    )


def _motion_ratio(first: Image.Image, second: Image.Image) -> float:
    first_rgba = first.convert("RGBA")
    second_rgba = second.convert("RGBA")
    first_pixels = cast(
        tuple[tuple[int, int, int, int], ...],
        first_rgba.get_flattened_data(),
    )
    second_pixels = cast(
        tuple[tuple[int, int, int, int], ...],
        second_rgba.get_flattened_data(),
    )
    changed = 0
    union = 0
    for first_pixel, second_pixel in zip(
        first_pixels,
        second_pixels,
        strict=True,
    ):
        if first_pixel[3] > 8 or second_pixel[3] > 8:
            union += 1
            if (
                max(abs(a - b) for a, b in zip(first_pixel, second_pixel, strict=True))
                > 12
            ):
                changed += 1
    return changed / union if union else 0.0


def _coefficient_of_variation(values: list[int]) -> float:
    mean = statistics.fmean(values)
    if mean == 0 or len(values) < 2:
        return 0.0
    return statistics.pstdev(values) / mean


def audit_pet(
    pet_dir: str | Path,
    *,
    policy: PetSightPolicy | None = None,
    chroma_key: RGB = (0, 0, 255),
) -> Report:
    """Audit real v2 atlas pixels across backgrounds and color-vision modes."""

    root = Path(pet_dir)
    effective_policy = policy or PetSightPolicy()
    report = Report(subject=str(root))
    validation = validate_pet(root, chroma_key=chroma_key)
    report.merge(validation, "validation")
    report.facts["policy"] = effective_policy.to_dict()
    if not validation.ok:
        return report

    manifest = validation.facts["manifest"]
    atlas_path = root / str(manifest["spritesheetPath"])
    with Image.open(atlas_path) as source:
        atlas = source.convert("RGBA")

    all_metrics: list[FrameMetrics] = []
    rows: dict[str, dict[str, Any]] = {}
    for row in ANIMATION_ROWS:
        cells = [
            atlas.crop(cell_box(row.index, column)).copy()
            for column in range(row.frame_count)
        ]
        metrics = [
            _frame_metrics(cell, row.name, column, effective_policy)
            for column, cell in enumerate(cells)
        ]
        all_metrics.extend(metrics)
        visible = [metric.visible_pixels for metric in metrics]
        baselines = [metric.baseline for metric in metrics]
        area_cv = _coefficient_of_variation(visible)
        baseline_span = max(baselines) - min(baselines)
        motion = [
            _motion_ratio(cells[index], cells[(index + 1) % len(cells)])
            for index in range(len(cells))
        ]
        duplicate_pairs = [
            f"{index}->{(index + 1) % len(cells)}"
            for index, ratio in enumerate(motion)
            if ratio == 0.0
        ]
        rows[row.name] = {
            "area_cv": round(area_cv, 5),
            "baseline_span": baseline_span,
            "motion_ratios": [round(value, 5) for value in motion],
            "mean_motion_ratio": round(statistics.fmean(motion), 5),
            "duplicate_pairs": duplicate_pairs,
        }
        if duplicate_pairs:
            report.add(
                "error",
                "petsight.animation.duplicate",
                f"{row.name} has identical adjacent frames: {', '.join(duplicate_pairs)}.",
                atlas_path,
                f"Regenerate the complete {row.name} row with visible state-appropriate motion.",
            )
        if statistics.fmean(motion) < effective_policy.minimum_motion_ratio:
            report.add(
                "error",
                "petsight.animation.inert",
                f"{row.name} mean motion ratio is {statistics.fmean(motion):.4f}.",
                atlas_path,
                f"Regenerate {row.name}; the loop is effectively static at pet size.",
            )
        if area_cv > effective_policy.maximum_area_cv:
            report.add(
                "error",
                "petsight.animation.size-pop",
                f"{row.name} visible-area coefficient of variation is {area_cv:.3f}.",
                atlas_path,
                f"Normalize scale across the complete {row.name} row.",
            )
        elif area_cv >= effective_policy.warning_area_cv:
            report.add(
                "warning",
                "petsight.animation.size-variation",
                f"{row.name} visible-area coefficient of variation is {area_cv:.3f}.",
                atlas_path,
                f"Review the {row.name} preview at normal display size.",
            )
        if not row.permits_vertical_travel:
            if baseline_span > effective_policy.maximum_baseline_span:
                report.add(
                    "error",
                    "petsight.animation.baseline-jump",
                    f"{row.name} baseline spans {baseline_span}px.",
                    atlas_path,
                    f"Re-register the complete {row.name} row against one lower-body anchor.",
                )
            elif baseline_span >= effective_policy.warning_baseline_span:
                report.add(
                    "warning",
                    "petsight.animation.baseline-variation",
                    f"{row.name} baseline spans {baseline_span}px.",
                    atlas_path,
                    f"Review the {row.name} preview for visible bobbing.",
                )

    neutral_row, neutral_column = NEUTRAL_LOOK_FRAME
    neutral_cell = atlas.crop(cell_box(neutral_row, neutral_column)).copy()
    all_metrics.append(
        _frame_metrics(
            neutral_cell,
            "neutral-look",
            neutral_column,
            effective_policy,
        )
    )

    worst_frame = min(all_metrics, key=lambda metric: metric.edge_contrast_p10)
    if worst_frame.edge_contrast_p10 < effective_policy.minimum_edge_contrast:
        report.add(
            "error",
            "petsight.contrast.edge",
            (
                f"{worst_frame.row}[{worst_frame.column}] has 10th-percentile edge "
                f"contrast {worst_frame.edge_contrast_p10:.2f} in "
                f"{worst_frame.worst_scenario}."
            ),
            atlas_path,
            "Strengthen the sprite outline or revise the failing palette boundary.",
        )
    elif worst_frame.edge_contrast_p10 < effective_policy.warning_edge_contrast:
        report.add(
            "warning",
            "petsight.contrast.edge-warning",
            (
                f"Worst edge contrast is {worst_frame.edge_contrast_p10:.2f} at "
                f"{worst_frame.row}[{worst_frame.column}] in "
                f"{worst_frame.worst_scenario}."
            ),
            atlas_path,
            "Inspect the generated PetSight matrix on the named scenario.",
        )

    for metric in all_metrics:
        if metric.coverage < effective_policy.minimum_coverage:
            report.add(
                "error",
                "petsight.coverage.too-small",
                f"{metric.row}[{metric.column}] covers only {metric.coverage:.1%} of its cell.",
                atlas_path,
                "Regenerate or re-register the row at the canonical pet scale.",
            )
        if metric.coverage > effective_policy.maximum_coverage:
            report.add(
                "error",
                "petsight.coverage.too-large",
                f"{metric.row}[{metric.column}] covers {metric.coverage:.1%} of its cell.",
                atlas_path,
                "Reduce the complete row at one shared scale to restore safe padding.",
            )

    report.facts["petsight"] = {
        "modes": list(_CVD_MATRICES),
        "rows": rows,
        "neutral_look_frame": {
            "row": neutral_row,
            "column": neutral_column,
        },
        "worst_edge_contrast": worst_frame.edge_contrast_p10,
        "worst_edge_scenario": worst_frame.worst_scenario,
        "frames": [asdict(metric) for metric in all_metrics],
    }
    return report


def _convert_image(image: Image.Image, matrix: tuple[float, ...]) -> Image.Image:
    red, green, blue, alpha = image.convert("RGBA").split()
    rgb = Image.merge("RGB", (red, green, blue))
    conversion_matrix = (
        matrix[0],
        matrix[1],
        matrix[2],
        0.0,
        matrix[3],
        matrix[4],
        matrix[5],
        0.0,
        matrix[6],
        matrix[7],
        matrix[8],
        0.0,
    )
    converted = rgb.convert("RGB", matrix=conversion_matrix).convert("RGBA")
    converted.putalpha(alpha)
    return converted


def render_matrix(
    pet_dir: str | Path,
    output: str | Path,
    *,
    policy: PetSightPolicy | None = None,
) -> Path:
    """Render representative real atlas cells across eight viewing scenarios."""

    root = Path(pet_dir)
    effective_policy = policy or PetSightPolicy()
    validation = validate_pet(root)
    if not validation.ok:
        raise ValueError("cannot render PetSight matrix for an invalid pet")
    manifest = validation.facts["manifest"]
    with Image.open(root / str(manifest["spritesheetPath"])) as source:
        atlas = source.convert("RGBA")

    scenarios = [
        (mode, background_name, matrix, background)
        for mode, matrix in _CVD_MATRICES.items()
        for background_name, background in effective_policy.backgrounds.items()
    ]
    cell_size = (
        max(1, round(CELL_WIDTH * effective_policy.display_scale)),
        max(1, round(CELL_HEIGHT * effective_policy.display_scale)),
    )
    left_gutter = 156
    top_gutter = 42
    gap = 8
    width = left_gutter + len(scenarios) * (cell_size[0] + gap) + gap
    height = top_gutter + len(ANIMATION_ROWS) * (cell_size[1] + gap) + gap
    sheet = Image.new("RGB", (width, height), (245, 247, 250))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (mode, background_name, _matrix, _background) in enumerate(scenarios):
        x = left_gutter + index * (cell_size[0] + gap)
        draw.text((x, 8), f"{mode}\n{background_name}", fill=(24, 30, 38), font=font)

    for row_index, row in enumerate(ANIMATION_ROWS):
        y = top_gutter + row_index * (cell_size[1] + gap)
        draw.text((10, y + cell_size[1] // 2 - 6), row.name, fill=(24, 30, 38), font=font)
        sample_column = 0 if row.index < 9 else (0 if row.index == 9 else 4)
        cell = atlas.crop(cell_box(row.index, sample_column))
        for scenario_index, (_mode, _background_name, matrix, background) in enumerate(scenarios):
            x = left_gutter + scenario_index * (cell_size[0] + gap)
            converted = _convert_image(cell, matrix)
            converted_background = _transform(background, matrix)
            panel = Image.new("RGBA", cell.size, (*converted_background, 255))
            panel.alpha_composite(converted)
            panel = panel.convert("RGB").resize(cell_size, Image.Resampling.LANCZOS)
            sheet.paste(panel, (x, y))

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, format="PNG", optimize=True)
    return target


def write_html_report(report: Report, output: str | Path, matrix_name: str | None = None) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    issues = "".join(
        (
            f'<li class="{html.escape(issue.severity)}"><code>{html.escape(issue.code)}</code> '
            f"{html.escape(issue.message)}"
            + (
                f"<br><strong>Repair:</strong> {html.escape(issue.repair)}"
                if issue.repair
                else ""
            )
            + "</li>"
        )
        for issue in report.issues
    )
    matrix = (
        f'<figure><img src="{html.escape(matrix_name)}" alt="PetSight background and '
        'color-vision comparison matrix"></figure>'
        if matrix_name
        else ""
    )
    payload = html.escape(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>PetSight report</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ max-width: 80rem; margin: 0 auto; padding: 2rem; line-height: 1.5; }}
    img {{ max-width: 100%; height: auto; border: 1px solid #8888; }}
    code, pre {{ font-family: ui-monospace, monospace; }}
    .error {{ color: #c62828; }} .warning {{ color: #9a6700; }}
    pre {{ overflow: auto; padding: 1rem; background: #7772; }}
  </style>
</head>
<body>
  <h1>PetSight report: {"PASS" if report.ok else "FAIL"}</h1>
  <p>Subject: <code>{html.escape(report.subject)}</code></p>
  <h2>Issues</h2>
  <ul>{issues or "<li>None</li>"}</ul>
  {matrix}
  <details><summary>Machine-readable evidence</summary><pre>{payload}</pre></details>
</body>
</html>
"""
    target.write_text(document, encoding="utf-8", newline="\n")
    return target
