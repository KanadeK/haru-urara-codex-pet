# PetSight

PetSight is a deterministic visual-accessibility and animation-integrity audit
for Codex v2 pets.

## Run it

```bash
urara-pet audit pet/haru-urara \
  --policy examples/petsight-policy.json \
  --json-out build/petsight-report.json \
  --matrix-out build/petsight-matrix.png \
  --html-out build/petsight-report.html
```

Exit code `0` means no errors. Warnings remain visible in JSON and HTML but do
not make the report fail. Exit code `1` means the pet or visual policy failed;
exit code `2` means the command could not be completed, for example because an
input path was missing or a policy was malformed.

## Scenarios

The default policy evaluates each outline under:

- normal vision;
- protanopia simulation;
- deuteranopia simulation;
- tritanopia simulation;

on a Codex-like dark background and a white paper background. PetSight reports
the worst 10th-percentile edge contrast rather than letting a few high-contrast
pixels hide a weak outline.

The color transforms are deterministic screening approximations, not medical
diagnoses and not a substitute for testing with users.

## Animation checks

Each state is checked independently:

- **duplicate** — adjacent frames have no changed visible pixels;
- **inert** — mean changed-pixel ratio is below policy;
- **size pop** — visible-area coefficient of variation is too high;
- **baseline jump** — non-jumping states move vertically beyond policy;
- **coverage** — a frame is too small or too large for a 192×208 cell.

Jumping and directional look rows allow intentional vertical travel according
to the canonical specification.

The dedicated neutral look frame at row 0, column 6 is audited for coverage
and contrast as a required cell, but it is not inserted into the six-frame
idle loop or graded as an animation transition.

## Policy

`examples/petsight-policy.json` contains every supported key:

```json
{
  "backgrounds": {
    "codex-dark": "#0D1117",
    "paper-light": "#FFFFFF"
  },
  "minimum_edge_contrast": 1.12,
  "warning_edge_contrast": 1.35,
  "minimum_motion_ratio": 0.002,
  "maximum_area_cv": 0.36,
  "warning_area_cv": 0.22,
  "maximum_baseline_span": 18,
  "warning_baseline_span": 10,
  "minimum_coverage": 0.015,
  "maximum_coverage": 0.82,
  "display_scale": 0.5
}
```

Unknown keys, malformed colors, empty background sets, invalid display scale,
or reversed contrast thresholds are rejected. Keep project policy under
version control so a passing result can be reproduced.

## Repair discipline

PetSight issue text includes a targeted repair. Regenerate or re-register the
complete failing row when animation continuity is involved. Do not:

- copy an unrelated state into a missing cell;
- clear a required cell;
- lower a threshold solely to turn CI green;
- apply repeated global chroma removal that erodes outline colors.

Run one correction, rebuild, and rerun both strict validation and PetSight.
