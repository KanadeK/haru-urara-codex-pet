# Contributing

Thank you for helping Haru Urara keep trying.

## Setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python scripts/verify.py
```

On Windows, invoke the environment's Python as
`.venv\Scripts\python.exe`. On macOS and Linux, use
`.venv/bin/python`.

## Pull requests

- Keep the installer recoverable and validate before every write.
- Add tests for behavior changes, including the failure path.
- Do not weaken v2 atlas, archive, or PetSight checks merely to make a fixture
  pass.
- Do not add copyrighted official art, ripped game assets, logos, or race
  numbers.
- Run `python scripts/verify.py` before opening a pull request.

Visual changes must include an updated contact sheet, direction QA, and
PetSight report. Code-only changes do not require regenerating the sprite.
