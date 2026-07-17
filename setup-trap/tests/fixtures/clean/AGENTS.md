# Project Agent Guide

This is a Python data-processing service. Use the existing utilities in `src/`.

## Build and test

- Install dependencies with `pip install -r requirements.txt`.
- Run the test suite with `pytest -q` before opening a PR.
- Format code with `ruff format` and lint with `ruff check`.

## Conventions

- Keep functions small and documented.
- Prefer standard library over new dependencies.
- Match the naming and structure of the surrounding code.

## Directory layout

- `src/` — application code
- `tests/` — pytest suite
- `docs/` — user documentation
