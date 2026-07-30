# Architecture

The repository has two deliverables that share one validation core:

```text
pet/haru-urara
  pet.json + spritesheet.webp
          │
          ▼
  strict v2 validation
    ├── PetSight ──► JSON / PNG / HTML evidence
    ├── packager ──► deterministic ZIP / .codex-pet
    └── installer ─► lock / stage / backup / replace / verify
```

## Modules

| Module | Responsibility |
| --- | --- |
| `spec.py` | Canonical 8×11 layout, cell geometry, frame counts, and direction order |
| `report.py` | Stable issue codes, severities, facts, repair text, and JSON serialization |
| `validation.py` | Manifest safety, v2 geometry, required/unused cells, hidden RGB, chroma, and size limits |
| `petsight.py` | Perceptual transforms, edge contrast, coverage, motion, scale, baseline, matrix, and HTML |
| `archive.py` | Deterministic building plus traversal, duplicate, symlink, size, and layout inspection |
| `install.py` | Source resolution, locks, staging, atomic replacement, backups, drift diagnosis, repair, and restore |
| `cli.py` | Human and machine-readable command-line interface |

## Pet format

The final atlas is 1536×2288 pixels:

- 8 columns × 11 rows;
- each cell is 192×208;
- rows 0–8 contain nine task states and 57 required frames;
- rows 9–10 contain 16 clockwise look directions;
- row 0, column 6 contains the dedicated neutral look frame;
- 74 cells are populated and 14 are deliberately transparent.

`pet.json` sets `spriteVersionNumber` to `2` and points to the lossless WebP.
Validation refuses unsafe relative paths, malformed field types, incorrect
geometry, empty required cells, or dirty unused cells.

## Installer transaction

Installation is recoverable by construction:

1. resolve a directory, repository, ZIP, or `.codex-pet`;
2. validate the source before acquiring the write lock;
3. copy only `pet.json` and `spritesheet.webp` into a unique staging directory;
4. validate the staged copy;
5. copy any current valid install into a content-addressed backup;
6. move the current install aside and atomically replace it with the stage;
7. validate the installed bytes;
8. on any exception, remove an invalid stage/install and restore the displaced
   installation.

The lock is pet-specific and has a bounded wait. Uninstall moves a valid
installation into the same backup area; restore validates a backup before
calling the normal install transaction.

## Archive safety and reproducibility

Archive inspection occurs before extraction and rejects:

- absolute paths and `..` traversal;
- duplicate member names;
- symbolic links;
- unexpected members;
- multiple or separated manifests and spritesheets;
- oversized compressed, member, or expanded payloads.

Release ZIP metadata uses a fixed timestamp and fixed permissions. Entries are
sorted, compression settings are fixed, and checksums cover exact member bytes.
The release gate builds twice after a deliberate pause and compares bytes.

## PetSight data flow

For every required cell PetSight:

1. extracts the alpha mask and inside outline;
2. transforms outline and background colors through four perception matrices;
3. calculates the 10th-percentile contrast for each scenario;
4. measures coverage, bounding box, centroid, and baseline;
5. compares adjacent frames for visible pixel motion;
6. aggregates duplicate, inert, size, and baseline findings by state.

No network, browser, GPU, or GUI is required. The same functions drive the CLI,
tests, and release gate.
