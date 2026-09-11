# BUILD_NOTES — SWE-Gate v0.1.0 (2026-09-11)

## What was built

`swe_gate` Python package (3.11+) with `swe-gate` console entry point:

- `swe_gate/gitdiff.py` — baseline resolution (explicit `--baseline` ref →
  merge-base with default branch → HEAD → empty tree) and changeset
  extraction: changed files, new-side changed line numbers, baseline
  contents. All layers consume only this delta.
- `swe_gate/layers/tampering.py` (L0) — AST diff of changed test files:
  deleted tests, reduced assertion counts, added skip/xfail
  markers/calls, statically-truthy assertions. Blocking.
- `swe_gate/layers/imports.py` (L1, lead feature) — AST walk of new imports;
  deterministic resolvers (relative-path, repo-local, stdlib,
  `find_spec`, `importlib.metadata`); unresolved → blocking. `--check-pypi`
  opt-in: 404 confirms (blocking), hit downgrades to advisory, network
  error stays blocking labeled "unverified (PyPI unreachable)". Offline
  default performs zero network I/O (asserted by test).
- `swe_gate/layers/signatures.py` (L2) — `pyright --outputjson` scoped to
  changed files; signature-family rules intersected with changed lines.
  pyright absent → labeled non-blocking `skipped`; stub gaps →
  `unverifiable`; pyright crash/timeout → `error` (exit 2).
- `swe_gate/layers/security.py` (L3) — bandit JSON + semgrep with in-repo
  rule pack `swe_gate/rules/ai-patterns.yml` (f-string SQL, shell=True
  interpolation, verify=False, pickle loads, hardcoded secrets, unsafe
  yaml.load, dynamic eval/exec). New HIGH blocks; MEDIUM/LOW advisory.
- `swe_gate/verdict.py` — exit code is a pure function of layer statuses;
  terminal/JSON/markdown renderers all lead with the per-layer table.
  The only derived number is a plain advisory-finding count, labeled
  "not a probability; never gates" in every format.
- `examples/` — seeded demo (`bash examples/run_demo.sh`): green pytest,
  then the gate failing with all four layers attributing findings.

## Test results

`python3 -m pytest tests/ -q` → **33 passed** (2026-09-11, Python 3.11.2,
bandit 1.9.4, semgrep 1.177.0, pyright 1.1.414). Covers the acceptance
criteria from the brief: one seeded failing example per layer asserting
exit 1 + correct layer attribution; delta tests per layer (pre-existing
debt never gates); determinism test (removing all advisory findings changes
no layer status and no exit code); graceful degradation (pyright missing →
skip, non-Python changeset → all n/a + exit 0, PyPI unreachable → blocking
"unverified"). Demo verified end-to-end; exits 1 with 6 blocking findings
across L0–L3.

## Known limitations (honest)

- **Real-LLM behavior: not benchmarked.** No empirical measurement of catch
  or false-positive rates on actual LLM-generated patches was run. The
  seeded tests/demo prove the mechanics, not field performance.
- The requirements doc at `/root/.openclaw/shared/builder-pipeline/requirements/`
  was **permission-denied in the build environment**; the build follows the
  dispatch brief. Interpretation choices are flagged in README
  "Ambiguities flagged during the build".
- L0 counts assertions; it will not catch semantic weakening that preserves
  assertion count (e.g. `== expected` → `is not None`).
- L1 checks the *import name* against PyPI; import→distribution aliasing
  (e.g. `PIL`/`Pillow`) is only resolved for installed packages.
- L2 signature checks are bounded by pyright's inference; untyped or
  stub-less third-party code reports `unverifiable`, not verified.
- L3 delta matching is line-based; a pre-existing vulnerable line that
  merely moves (renamed file handled; big refactors not) can resurface as
  "new".
- Python-only. Non-Python changesets pass with `n/a` by design.
- Stretch layers (L4 import-linter, L5 interrogate, L7 mutation) not built.
