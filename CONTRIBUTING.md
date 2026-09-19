# Contributing

## Setup

Each repository gets its own virtual environment. Do not reuse a virtual
environment across repositories — a shared one hides missing dependencies
until CI catches them.

```bash
python -m venv .venv
. .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running the checks

This is what CI runs on every push, on Python 3.10 and 3.12:

```bash
python -m compileall -q .
python -m pytest -q
```

Run both before opening a PR.

## Adding a check or a fix

Start with a failing test in `tests/` (pytest), then write the fix. Tests run
against saved HTML fixtures in `tests/fixtures/`, not the network — keep it
that way.

## Commit style

Short, lowercase, often `type: description` (`feat`, `fix`, `test`, `docs`,
`chore`), sometimes a plain descriptive sentence. No strict conventional-commits
enforcement. Examples from this repo's history:

- `feat: retries with backoff, de-duplication and the CLI`
- `test: parser, pipeline and retry coverage (21 tests, no network)`
- `README: drop the boilerplate intro line`

## Pull requests

- Keep changes scoped to one thing.
- CI must pass (byte-compile + pytest, on 3.10 and 3.12).
- Do not commit secrets or credentials (`.env`, API keys, proxy URLs with
  embedded credentials).
- Do not commit target-site cookies or session data under `sample_output/` —
  only clean, deduplicated CSV output belongs there.
