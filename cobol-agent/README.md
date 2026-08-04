# Cobalt

**AI-powered COBOL comprehension and translation, with the numeric semantics
done by deterministic code instead of model guesswork.**

Cobalt reads legacy COBOL (program + copybooks), decodes every `PICTURE`
clause itself — packed decimal, assumed decimal points, signs, OCCURS,
REDEFINES, 88-levels — and hands the LLM a pre-computed data dictionary and
PERFORM graph. The model explains business rules and writes Java; it never
gets to decide what `PIC S9(7)V99 COMP-3` means, because that answer
(`BigDecimal`, scale 2, truncate with `RoundingMode.DOWN`) is computed by
code and pinned by tests.

That is the differentiation in one sentence: **generic LLM translators let
the model infer COBOL data semantics from raw source; Cobalt computes those
semantics deterministically and constrains the model to them.**

## What Cobalt does

- `cobalt explain SOURCE.cbl` — plain-English documentation: what the program
  does, its data structures in business terms, the encoded business rules
  (with truncation semantics called out), and the PERFORM control flow.
- `cobalt translate SOURCE.cbl --to java` — idiomatic Java 17. All COMP-3 and
  V-scaled fields become `BigDecimal` with explicit scale; COBOL's default
  truncating arithmetic becomes `.setScale(n, RoundingMode.DOWN)`; `ROUNDED`
  becomes `HALF_UP`; 88-levels become predicates; OCCURS becomes fixed-size
  collections with the 1-based→0-based subscript shift.
- `cobalt test SOURCE.cbl` — JUnit 5 characterization tests using exact
  `BigDecimal` assertions, seeded from a GnuCOBOL golden master when one is
  available (and honestly labeled when it is not).
- `cobalt inspect SOURCE.cbl` — show the assembled context (data dictionary,
  PERFORM graph, semantics rules) with no LLM call.
- `cobalt demo` — run the pipeline end-to-end on the bundled sample.

## What Cobalt is NOT

- **Not a compiler or a rules engine.** The final translation comes from an
  LLM and can be wrong. Every output needs human review before it goes near
  production.
- **Not a mainframe migration suite.** No CICS, no embedded SQL (DB2), no
  VSAM/file I/O translation, no JCL. Batch-style computational COBOL only.
- **Not z/OS-verified.** The bundled golden master comes from GnuCOBOL on
  Linux. IBM Enterprise COBOL differs in edge cases (invalid packed data,
  some intermediate-result rules).
- **Not a full COBOL parser** when running in pure-Python fallback mode: the
  fallback covers the Data Division plus paragraph/PERFORM extraction, not
  every statement form (see Architecture below).
- **Not benchmarked against real models.** The test suite mocks the LLM
  provider by design. Real-LLM behavior: not benchmarked.

## Quickstart

Cobalt is not on PyPI; install from the monorepo source:

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd cobol-agent && pip install -e .
```

Then, on the bundled healthcare-claims sample (three commands):

```bash
export COBALT_MODEL=anthropic/claude-sonnet-4-6      # any LiteLLM model string
cobalt explain assets/samples/claimcalc.cbl -I assets/samples/copy
cobalt translate assets/samples/claimcalc.cbl -I assets/samples/copy --to java
```

No API key yet? `cobalt demo --skip-llm` and `cobalt inspect` run the full
parse/assembly pipeline with zero API calls.

Model selection is only via environment variables (LiteLLM format) — no
model name is hardcoded anywhere in a prompt:

```bash
export COBALT_MODEL=anthropic/claude-sonnet-4-6          # any hosted model
# or a local LiteLLM proxy:
export COBALT_MODEL=litellm/sonnet45
export COBALT_API_BASE=http://localhost:4000
export COBALT_API_KEY=sk-...
```

## Architecture

```
                        ┌───────────────────────────────┐
  SOURCE.cbl            │           PARSER              │
  copy/*.cpy   ───────► │  java -jar cobalt-parser-v0   │──┐
                        │  (ProLeap/ANTLR4, subprocess) │  │  cobalt-parser-v0
                        ├───────────────────────────────┤  │  JSON contract
                        │  cobalt/parser/fallback.py    │──┤  (schema.py
                        │  (pure Python, no JVM:        │  │   validates both)
                        │   Data Division + PERFORMs)   │  │
                        └───────────────────────────────┘  │
                                                           ▼
                        ┌───────────────────────────────────────────┐
                        │        ASSEMBLER (deterministic)          │
                        │  cobalt/assembler.py + cobalt/types.py    │
                        │  • PIC → Java type table (COMP-3 rules)   │
                        │  • PERFORM call tree                      │
                        │  • REDEFINES / 88-level annotations       │
                        │  • truncation-semantics rulesheet         │
                        └───────────────────────────────────────────┘
                                                           │ context block
                                                           ▼
                        ┌───────────────────────────────────────────┐
                        │   LLM (LiteLLM, COBALT_MODEL env var)     │
                        │   explain │ translate --to java │ test    │
                        └───────────────────────────────────────────┘
```

Both parser backends emit the same JSON contract (`cobalt/schema.py`,
`cobalt-parser-v0`), so everything downstream is parser-agnostic. The
front door (`cobalt/parser/__init__.py`) uses the ProLeap JAR when
`assets/cobalt-parser-v0.jar` exists and `java` is on PATH, otherwise the
Python fallback — or force one with `--parser java|fallback`.

### The Java parser wrapper

`java-parser/` holds a <200-line wrapper (`ParserCli.java`) around the
[ProLeap COBOL parser](https://github.com/uwol/proleap-cobol-parser)
(Apache-2.0, ANTLR4-based). Build it with:

```bash
java-parser/build.sh        # needs JDK 17+, Maven, network (JitPack)
```

The script drops `assets/cobalt-parser-v0.jar` where the Python side looks
for it. If you can't build it, nothing breaks — the fallback parser handles
fixed-format COBOL-85 Data Divisions, COPY resolution, and PERFORM graphs,
which is enough for programs like the bundled sample. The fallback does
*not* handle continuation lines, `COPY REPLACING`, free-format source, or
nested programs; those need the ProLeap backend.

## The bundled sample

`assets/samples/claimcalc.cbl` (+ `copy/CLAIMREC.cpy`, `copy/BENFTABL.cpy`)
is a healthcare claim adjudicator built to exercise the hard parts: COMP-3
money arithmetic with COBOL truncation (`1234.56 × 0.80 = 987.648` stores
`987.64`, not `.65`), an OCCURS/REDEFINES benefit table, 88-level condition
names, and a multi-paragraph PERFORM structure.

`assets/samples/golden/expected_output.txt` is a **real golden master**: the
verbatim stdout of that program compiled and run with GnuCOBOL 3.1.2 (see
`golden/PROVENANCE.md`; regenerate with `golden/regenerate.sh`). The test
suite re-derives every number in it with exact decimal arithmetic.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

132 tests; no API calls (the provider is mocked) and no JVM (parser input is
canned JSON or the Python fallback). Output produced under the mock provider
is labeled `[MOCK LLM OUTPUT …]` — it is not model output and no real-LLM
quality numbers are claimed anywhere in this repo.

## Honest limitations

- **GnuCOBOL-verified ≠ z/OS-verified.** All numeric verification is against
  GnuCOBOL on Linux.
- **Human review is required.** The deterministic layer pins types and
  rounding; the LLM still writes the logic, and LLMs make mistakes.
- **No CICS, no SQL, no VSAM.** Programs using them will parse partially at
  best.
- **REDEFINES is flagged, not solved.** Cobalt picks the layout the
  procedure code uses and marks the other for human review.
- **Real-LLM behavior: not benchmarked.** Fixture/mock results say nothing
  about live model accuracy.

## Roadmap (out of scope for v0.1)

- v0.2: `--to python` translation target (the CLI plumbing already exists).
- Batch mode over whole codebases; cross-program call graphs.
- CICS/DB2/VSAM awareness (detection and honest refusal first, translation
  later).
- z/OS-dialect golden masters via IBM COBOL where licensing permits.

## Attribution

- [ProLeap COBOL parser](https://github.com/uwol/proleap-cobol-parser) —
  Apache-2.0 — powers the Java parser backend.
- [GnuCOBOL](https://gnucobol.sourceforge.io/) — golden-master generation.
- [ANTLR4](https://www.antlr.org/) — underlying parser generator (via ProLeap).
- [LiteLLM](https://github.com/BerriAI/litellm) — provider abstraction.

License: **Elastic License 2.0** (source-available) — see [LICENSE](LICENSE). You may use, modify, and self-host Cobalt freely; you may not offer it to third parties as a hosted or managed service. Bundled third-party components (ProLeap, ANTLR4, LiteLLM) remain under their own permissive licenses; GnuCOBOL is used only as an external tool and is not distributed with Cobalt.
