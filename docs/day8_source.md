# Day 8 source provenance

- Upstream: https://github.com/VinUni-AI20k/K5-Day8-From-Workflows-to-Agents
- Revision: `034c6c421c198dae67a9211d15e2587d5a378972`.
- Verified against upstream HEAD with `git ls-remote` during Task 1.
- Imported only `src/` using `git archive` from that exact revision, already present in the adjacent team repository's history. The team's HEAD was not used; the team repository was not modified.
- All 63 upstream source files were imported without overwriting existing Lab 9 files. Preserve these files unchanged while completing Lab 9.

## Local environment

Use Python 3.13 and the virtual environment at `src/.venv/`. From `src/`, run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-lab9.txt
.\.venv\Scripts\python.exe -m lab9.smoke
.\.venv\Scripts\python.exe -m lab9.evalset --build
```

The virtual environment is ignored by Git. At M0, `failure_modes` is intentionally empty; completing taxonomy and passing `evalset --check` belongs to M1.

## Task 1 verification

- Python: 3.13.16; pydantic-evals: 2.68.0.
- Imported files: all 63 match the upstream Git archive byte for byte.
- `lab9.smoke`: `M0 PASS`, exit 0.
- `pip check`: no broken requirements, exit 0.
- `lab9.evalset --build`: 14 items, 14 separate labels, exit 0. Also verified unique item IDs, complete label mapping and no inline labels.
- GitHub Actions enabled: `true` from the fork's actions permissions API.
- Lab 9 logic/spec files unchanged. No full test suite or CI run at M0; grader/statistics TODOs remain for later tasks.
