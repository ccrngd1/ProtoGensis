# Agent instructions — payments-service

## Build and test

- Run `make test` before every commit; it must exit 0.
- Use `ruff check .` for linting; do not add new `# noqa` comments.
- New functions require a test that exercises the error path, because
  untested error paths caused the 2025-11 refund outage.

## Code style

- Use 4-space indentation in Python files (enforced by ruff, rule E111).
- Never commit directly to `main`; open a PR from a feature branch, because
  branch protection blocks direct pushes and CI only runs on PRs.
- Prefer `pathlib.Path` over `os.path` in new code.

## Database

- Never run migrations against the production database from a dev machine,
  because migrations are applied by the deploy pipeline with a backup step.
- Add new columns as nullable first, then backfill, then add constraints.

## When stuck

- Read `docs/runbook.md` for incident procedures.
- Ask in `#payments-eng` before changing the ledger schema.
