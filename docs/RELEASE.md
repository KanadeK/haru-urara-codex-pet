# Release process

Releases are produced only from a clean, reviewed commit.

## Local gate

```bash
python -m pip install -e ".[dev]"
python scripts/verify.py
```

`verify.py` creates release candidates in a temporary directory, builds
deterministic pet archives twice with a deliberate delay, compares bytes,
inspects archive members and internal metadata, builds wheel/sdist, verifies
the bundled pet, and checks `SHA256SUMS`. Run
`python scripts/package_release.py --output-dir dist` after the gate to retain
the same verified artifact set locally.

Before tagging, also verify identity and history:

```bash
git status --short
git log -1 --format=fuller
git shortlog -sne HEAD
git log --format=%B | rg -i "co-authored-by"
```

The expected sole author/committer is:

```text
KanadeK <121669563+KanadeK@users.noreply.github.com>
```

## Tag and GitHub Release

1. Push the exact clean commit to `main`.
2. Wait for CI and security workflows to pass.
3. Create annotated tag `vX.Y.Z` on that commit and push it.
4. The release workflow rebuilds from the tag and uploads:
   - `.codex-pet`;
   - folder-preserving pet ZIP;
   - wheel and sdist;
   - PetSight JSON, HTML, and PNG;
   - `SHA256SUMS`.
5. Download every uploaded asset into a new directory.
6. Compare its SHA-256 with the uploaded `SHA256SUMS`.
7. Verify the GitHub Release tag target, public repository visibility, workflow
   status, and contributor list.

A successful local build or green static check is not a public release.

## Determinism

The deterministic check is deliberately time-separated. It catches accidental
wall-clock timestamps that two same-second builds can hide. Verification also
opens each ZIP and checks member names, timestamps, permissions, sizes, and
content hashes.

Python wheel/sdist reproducibility is reported separately because build
backends may include format-specific metadata. The release gate still verifies
their contents and bundled pet bytes.

## Failure handling

- If CI fails, do not move the tag. Fix the source, rerun the full gate, commit,
  and tag a new version.
- If an uploaded checksum differs, delete the broken release asset, rebuild
  from the tagged commit, regenerate `SHA256SUMS`, and reverify every asset.
- If the tag points to the wrong commit, stop publication, delete only the
  incorrect remote tag/release after resolving its exact target, then recreate
  both from the verified commit.
- If GitHub authentication is unavailable, preserve `dist/`, the clean commit,
  and the gate report; do not claim publication.
