# Troubleshooting and repair

Start with machine-readable diagnostics:

```bash
urara-pet doctor --source haru-urara.codex-pet --json
urara-pet validate pet/haru-urara --json
urara-pet audit pet/haru-urara --json
```

## Installer and archive

| Issue or symptom | Meaning | Repair |
| --- | --- | --- |
| `install.missing` | Haru Urara is not installed | Run `urara-pet install --source <verified source>` |
| `install.drift` | Installed bytes differ from the selected source | Run `urara-pet repair --source <same verified source>` |
| another installation holds the lock | A concurrent installer owns the pet lock | Wait for it to finish; if the process crashed, confirm no installer is running, then remove only `.haru-urara.install.lock` |
| `archive.path` | Archive contains an absolute or traversal path | Delete the archive and download the release asset again |
| `archive.duplicate` | A member name occurs more than once | Rebuild with `urara-pet package`; do not extract manually |
| `archive.symlink` | Archive contains a symbolic link | Reject the source and use an official release asset |
| `archive.extra-members` | Archive contains files outside the two pet files/checksum | Rebuild from `pet/haru-urara` |
| `archive.*-too-large` | Compressed or expanded limits were exceeded | Re-encode the atlas as lossless WebP and rebuild; do not raise limits without review |

To recover:

```bash
urara-pet uninstall
urara-pet restore
```

Uninstall is recoverable: it moves the verified installation into
`$CODEX_HOME/pets/.backups/haru-urara/`. Restore selects the newest valid
backup unless `--backup` is supplied.

## Manifest and atlas

| Issue code | Repair |
| --- | --- |
| `manifest.missing` / `manifest.unreadable` | Restore `pet.json` from the same release as the spritesheet |
| `manifest.*.type` | Replace the manifest; do not coerce malformed values in place |
| `manifest.sprite-version` | Use the shipped v2 manifest with `spriteVersionNumber: 2` |
| `manifest.spritesheet-path` / `manifest.spritesheet-escape` | Set a safe in-folder path, normally `spritesheet.webp` |
| `atlas.missing` / `atlas.unreadable` | Restore `spritesheet.webp` and verify the release SHA-256 |
| `atlas.geometry` | Rebuild the exact 1536×2288, 8×11 atlas with 192×208 cells |
| `atlas.required-empty` | Restore or regenerate the complete named state row |
| `atlas.unused-dirty` | Clear only unused slots to transparent black; row 0, column 6 is the required neutral look frame |
| `atlas.hidden-rgb` | Set RGB to zero wherever alpha is zero, then rebuild once |
| `atlas.chroma` | Run the documented single despill pass; repeated passes can damage the outline |

## PetSight

| Issue code | Repair |
| --- | --- |
| `petsight.contrast.edge` | Strengthen the complete sprite outline or revise the failing palette boundary |
| `petsight.contrast.edge-warning` | Inspect the generated matrix at the named mode/background |
| `petsight.animation.duplicate` | Regenerate the complete state row with distinct adjacent poses |
| `petsight.animation.inert` | Increase state-appropriate motion without changing identity or scale |
| `petsight.animation.size-pop` | Normalize every frame in the named row against one reference scale |
| `petsight.animation.baseline-jump` | Re-register the row against one lower-body anchor |
| `petsight.coverage.too-small` / `too-large` | Resize and re-register the complete row, keeping safe margins |

After a visual repair, run:

```bash
urara-pet validate pet/haru-urara
urara-pet audit pet/haru-urara \
  --matrix-out build/petsight-matrix.png \
  --json-out build/petsight-report.json
python scripts/verify.py
```

## Development gate failures

- **Ruff**: run `python -m ruff check . --fix`, inspect the diff, then rerun
  without `--fix`.
- **Mypy**: fix the reported type boundary; do not add broad `Any` or global
  ignores.
- **Coverage**: add a behavior test for the missing branch; do not lower the
  configured threshold.
- **Nondeterministic artifact**: compare ZIP member timestamps, order,
  permissions, compressed bytes, and `SHA256SUMS`. Build twice with at least a
  one-second separation.
- **Wheel missing the pet**: confirm the wheel contains
  `haru_urara_pet/bundled_pet/pet.json` and `spritesheet.webp`, then rebuild
  from a clean `dist/`.
- **Checksum mismatch**: delete the local artifact and download it again. Never
  repair an asset while keeping its old checksum.
