# SWE-Gate

> **📦 This project has moved to its own repository: [ccrngd1/swe-gate](https://github.com/ccrngd1/swe-gate).** This copy in ProtoGensis is an archive and is no longer updated. Clone with `git clone https://github.com/ccrngd1/swe-gate.git`.

**A post-test-pass deterministic verification gate for AI-specific coding defects.**

Your test suite passed. That is exactly when AI-generated patches are most
dangerous: the failure modes LLMs are prone to — hallucinated imports,
plausible-but-wrong call signatures, quietly weakened tests, injected
`shell=True` glue — are precisely the ones a green test run does not surface.

SWE-Gate runs **after** the tests, diffs the working tree against a baseline,
and renders one deterministic verdict. The underlying scanners (`ast`,
`importlib`, pyright, bandit, semgrep) are all well-known tools — that is the
point. The value is the **orchestration**: tuning them to AI failure modes,
gating only on *new* findings, and collapsing everything into a single
post-test pass/fail with clean exit codes. No LLM anywhere in the gating path.
Same diff in, same verdict out, every time.

## The four layers

| Layer | Defect class | How | Blocking |
|---|---|---|---|
| **L0** | Test tampering | AST-diff changed test files vs baseline: deleted tests, removed assertions, added `skip`/`xfail`, trivially-true assertions | yes |
| **L1** | Import hallucination *(lead feature)* | AST walk of new imports; resolve via stdlib list, `importlib.util.find_spec`, `importlib.metadata`, repo-local modules; optional PyPI existence check | yes |
| **L2** | Signature mismatch | `pyright --outputjson` scoped to changed files; arg-count / attribute / argument-type / return-type errors intersecting changed lines | yes |
| **L3** | Security patterns | bandit + a curated semgrep rule pack (`swe_gate/rules/ai-patterns.yml`): f-string SQL, `shell=True` interpolation, `verify=False`, `pickle.loads`, hardcoded secrets | new HIGH blocks; MEDIUM/LOW advisory |

**Delta principle:** every layer gates only on findings *new* versus the
baseline (git merge-base with the default branch, or `--baseline <ref>`).
Pre-existing debt never fails the gate.

## Install

Not published to PyPI. Install from source:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd swe-gate
pip install -e .          # bandit + semgrep come along as dependencies
pip install -e '.[pyright]'   # optional: enables Layer 2 (or `npm i -g pyright`)
```

Without pyright, Layer 2 degrades to a labeled, non-blocking `SKIP`.

## Usage

```bash
# after your test suite passes:
swe-gate run                          # gate the current repo vs merge-base
swe-gate run --baseline main~3        # explicit baseline ref
swe-gate run --format md              # markdown for a PR comment (also: json)
swe-gate run --layers 0,1             # subset of layers
swe-gate run --check-pypi             # opt-in network check of unresolved imports
```

Exit codes: **0** pass · **1** gate failed (new blocking findings) · **2** tool/scan error.

A changeset with no Python files reports `n/a (no Python in scope)` for every
layer and exits 0.

### `--check-pypi` semantics

The default is offline-safe: an import that resolves to no installed package,
stdlib module, or repo-local module blocks and is labeled
`unverified against PyPI`. With `--check-pypi` (the only code path that
touches the network), a PyPI 404 confirms the hallucination (stays blocking);
a hit downgrades it to an advisory "exists on PyPI but is not installed —
verify it is a declared dependency"; a network error keeps it blocking,
labeled `unverified (PyPI unreachable)`.

## Demo: green tests, four defects

```bash
bash examples/run_demo.sh
```

Builds a small note-store repo, commits a clean baseline, applies a
plausible-looking patch seeded with one defect per layer (hallucinated
`notesync_cloud` import, missing argument in an internal call, a gutted
test, `subprocess.run(f"...", shell=True)`), then shows `pytest` passing and
`swe-gate` failing with all four layers attributing their finding.

## Sample output

```
SWE-GATE: FAILED — 6 new blocking finding(s)
baseline: da1d7eede273

layer  name                  status  new blocking  detail
---------------------------------------------------------
L0     test tampering        FAIL    2             1 changed test file(s) compared against baseline
L1     import hallucination  FAIL    1             3 new import(s) checked across 2 changed file(s)
L2     signature mismatch    FAIL    1             pyright checked 2 changed file(s)
L3     security patterns     FAIL    2             bandit + semgrep over 2 changed file(s); new findings only

  BLOCKING [L1/import-hallucinated] app/export.py:9: import 'notesync_cloud' resolves to no installed package, ...
  ...
```

The advisory finding count at the bottom of a verdict is a plain count of
non-blocking findings. It is not a probability, not a confidence measure, and
never affects the gate decision.

## Determinism guarantees

* The exit code is a pure function of layer statuses; a layer's status is a
  pure function of its **blocking** findings. Advisory findings can be
  deleted wholesale without changing any verdict (tested in
  `tests/test_verdict_and_cli.py::TestDeterminism`).
* No LLM, no scoring model, no randomness in the gating path.
* Missing optional tooling degrades to labeled `SKIP`/`UNVERIFIABLE`
  statuses — never a silent pass, never a spurious failure.

## Related work

Background on the defect classes this gate targets (import hallucination in
particular): arXiv 2503.15223, arXiv 2410.06992, Spracklen et al. "We Have a
Package for You!", arXiv 2605.17062, arXiv 2506.11022.

## Ambiguities flagged during the build

The authoritative requirements document
(`/root/.openclaw/shared/builder-pipeline/requirements/2026-09-11-swe-gate-requirements.md`)
was **not readable from the build environment** (permission denied at build
time). This implementation follows the dispatch brief's summary of it.
Decisions that the full document may specify differently:

1. **Missing pyright semantics** — the brief allowed either exit-2 semantics
   or a labeled skip (AC #5 unseen). Implemented as a labeled, non-blocking
   `SKIP`, consistent with "degrade gracefully"; an actual pyright *crash*
   (unparseable output, timeout) is a layer `error` → exit 2.
2. **Layer 0 scope** — "weakened assertion" is implemented as: fewer
   assertions in a surviving test than at baseline, plus statically-truthy
   assert conditions. Semantic weakening (e.g. `==` loosened to `!=`) with
   the same assertion count is not detected.
3. **Trivially-true assertions** are flagged even in brand-new test files
   (nothing to diff against, but `assert True` is never legitimate).
4. **`--check-pypi` name mapping** — the check queries the import name
   against PyPI directly; import-name → distribution-name aliasing (e.g.
   `PIL` → `Pillow`) is handled for *installed* packages via
   `importlib.metadata`, but not for uninstalled ones.
5. **Stretch layers** (interrogate docs coverage, import-linter architecture,
   mutation micro-batch) were not built — MVP first, per the brief.

## License

MIT — see [LICENSE](LICENSE).
