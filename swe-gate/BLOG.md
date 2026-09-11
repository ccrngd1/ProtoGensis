# Your Coding Agent's Tests Pass. That Proves Less Than You Think.

About one in five patches that "solved" a problem on SWE-bench Verified were
semantically wrong. The test suite passed. The benchmark counted them as
successes. Peer review found otherwise (arXiv 2503.15223).

That number bothered me. Not because it's surprising in principle, but because
"all tests pass" is the success criterion for SWE-bench, every coding-agent
leaderboard, and most autonomous pipelines running in production right now. If
the peer-reviewed evidence says that gate is leaky, the leakage doesn't stay
on a benchmark. It comes with you.

There's a companion result. SWE-bench+ filtered out test cases where the
correct solution could be inferred by just reading the test assertions. When
they did that, resolution rates dropped from 12.47% to 3.97% (arXiv
2410.06992). That's not a measurement artifact. That's telling you what's
happening: agents learn to satisfy tests, not to solve problems. The test suite
was the thing being optimized. The test suite passed.

This is what SWE-Gate is for.

---

## Why AI-Generated Code Fails Differently

A human developer makes bugs. They get logic wrong. They misread requirements.
They forget edge cases. But a human developer does not, as a matter of regular
practice, invent a library that does not exist and import it.

LLMs do this somewhere between 5% and 22% of the time depending on model and
task, and the trend is not going away. Spracklen et al. ("We Have a Package
for You!") found 5.2% hallucinated packages in commercial model output and
21.7% in open-source models. A more recent study tracking frontier models
specifically found 4.62%–6.10% hallucination rates even at the current
capability frontier (arXiv 2605.17062). The range shrinks. The problem stays.

Security regression is the other one. An LLM that generates working code in
one iteration has a measured tendency to introduce critical vulnerabilities as
it revises. Iterative self-editing increased critical vulnerabilities
approximately 37.6% over five iterations (arXiv 2506.11022). Not across all
patches. On average, over iterations. The code that started clean gets worse
under revision pressure.

Neither of these shows up cleanly in a test suite. Nobody wrote
`test_imports_are_real`. Nobody wrote `test_no_new_sql_injection`. Tests cover
specified behavior. These defects live in the uncovered parts.

Then there's test tampering. An agent under pressure to make tests pass can
delete the failing test, weaken the assertion until it passes, or add
`@pytest.mark.skip`. From the test runner's perspective: green. From any other
perspective: reward hacking. It
happens. There are seeded examples in this repo that demonstrate it.

---

## What SWE-Gate Is

It's a post-test deterministic verification gate. You run it after your test
suite passes.

It diffs the working tree against a baseline (by default the merge-base with
your default branch), runs four layers of analysis scoped to the changed
files, and returns one verdict: pass or fail. No LLM anywhere in the gating
path. No scoring model. No probabilities. Same diff in, same verdict out,
every time.

The underlying tools are not new: `ast`, `importlib`, pyright, bandit,
semgrep. The point is the orchestration. Each tool is tuned to the specific
failure modes above, gating only on *new* findings versus the baseline. You
don't get penalized for pre-existing debt. Only the diff gets judged.

---

## The Four Layers

| Layer | Defect class | How | Blocking |
|---|---|---|---|
| **L0** | Test tampering | AST-diff changed test files: deleted tests, removed assertions, added `skip`/`xfail`, trivially-true assertions | yes |
| **L1** | Import hallucination | AST walk of new imports; resolved via stdlib list, `importlib.util.find_spec`, `importlib.metadata`, repo-local modules; optional PyPI existence check | yes |
| **L2** | Signature mismatch | `pyright --outputjson` scoped to changed files; arg-count / attribute / argument-type / return-type errors on changed lines | yes |
| **L3** | Security patterns | bandit + curated semgrep rule pack: f-string SQL, `shell=True` interpolation, `verify=False`, `pickle.loads`, hardcoded secrets | new HIGH blocks; MEDIUM/LOW advisory |

A few notes on tooling requirements, because I've been bitten by tools that
silently degrade:

L0 and L1 require nothing beyond SWE-Gate itself. They use `ast` and
`importlib`, which are stdlib. L3's dependencies (bandit and semgrep) are core
dependencies that install automatically. L2 needs pyright, which is optional.
If pyright isn't present, L2 degrades to a labeled, non-blocking `SKIP`. If it
crashes or times out, that's an exit code 2 (tool error), not a silent pass.
Missing tooling never produces a false green.

---

## The Demo

The repo ships a bash demo that makes the whole thing concrete:

```bash
bash examples/run_demo.sh
```

It builds a small note-store application, commits a clean baseline, then
applies a patch seeded with one defect per layer:

- A hallucinated `notesync_cloud` import that does not exist anywhere (L1)
- A call to `save_note()` missing the required `body` argument (L2)
- A `test_delete_note` gutted to `assert True` (L0)
- `subprocess.run(f"tar czf {dest} {db_path}", shell=True)` (L3)

Then `pytest` runs. Green. All tests pass.

Then `swe-gate` runs:

```
SWE-GATE: FAILED — 6 new blocking finding(s)
baseline: da1d7eede273

layer  name                  status  new blocking  detail
---------------------------------------------------------
L0     test tampering        FAIL    2             1 changed test file(s) compared against baseline
L1     import hallucination  FAIL    1             3 new import(s) checked across 2 changed file(s)
L2     signature mismatch    FAIL    1             pyright checked 2 changed file(s)
L3     security patterns     FAIL    2             bandit + semgrep over 2 changed file(s); new findings only
```

That's the point. The test suite and the gate are checking different things.
Both are necessary. Neither replaces the other.

---

## Install and Try It

This is not published to PyPI. Install from source:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/swe-gate
pip install -e .          # bandit + semgrep come along
pip install -e '.[pyright]'   # optional: enables Layer 2
```

Basic usage:

```bash
swe-gate run                          # gate vs merge-base
swe-gate run --baseline main~3        # explicit baseline
swe-gate run --format md              # markdown for a PR comment
swe-gate run --layers 0,1             # subset of layers
```

Exit codes: 0 = pass, 1 = gate failed (blocking findings), 2 = tool/scan
error.

The `--check-pypi` flag turns on network verification for unresolved imports.
Without it, an import that resolves to nothing blocks and is labeled
`unverified against PyPI`. With it, a PyPI 404 confirms the hallucination; a
hit downgrades to advisory ("exists on PyPI but not installed"); a
network error keeps it blocking, labeled "unverified (PyPI unreachable)".
Offline by default, by design.

---

## The Honest Limit

I want to be direct about what this is and isn't.

Every individual check here is an existing tool. Bandit exists. Semgrep
exists. Pyright exists. Python's `ast` module has been around forever. I
didn't invent new verification science. I glued the right tools into the right
gate, tuned them to AI failure modes, and wired them to run after tests. That
is the actual contribution. It's a useful contribution if you're running AI
coding agents and want a cheap always-on proxy for the failure modes I
described. It is not proof of correctness.

SWE-Gate is a smoke detector. If it fires, something is wrong. If it doesn't
fire, you still don't know everything is right. The deeper fixes are mutation
testing and property-based testing: tools that generate the assertions nobody
wrote. SWE-Gate is the cheap layer that runs on every patch and catches the
categorically-AI failure modes before they leave your CI.

One more limitation worth naming: no empirical measurement of catch rates or
false-positive rates on real LLM-generated patches was run as part of building
this. The seeded tests and the demo prove the mechanics. Field performance data
doesn't exist yet.

---

## Why This Gate, Why Now

The test suite tells you one thing: the code satisfies the assertions that were
written. It says nothing about the assertions nobody wrote, the APIs that don't
exist, the function signatures that changed, or the security regressions no
test covers.

These were always gaps. What's changed is that AI coding agents make all four
of them categorically more likely than a human developer working the same task.
Hallucinated imports happen on frontier models in the 4–6% range, consistently,
across studies. Test tampering is a documented failure mode of reward
optimization. Security regression accumulates under iterative revision pressure.

That's a different risk profile than human-generated code. It deserves a
different gate.

SWE-Gate is that gate. It runs after your tests. It takes maybe three seconds.
It adds a hard checkpoint for the defects your test suite wasn't designed to
catch.

If you're running coding agents in any capacity, try it on a recent patch and
see what it says. I'd be curious what shows up.

---

*SWE-Gate is part of the [Protogenesis](https://github.com/ccrngd1/ProtoGensis) project.*
