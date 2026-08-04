# I Built an AI Agent to Read the COBOL Nobody Left Alive Understands

*By CC | August 2026*

---

Here's the thing about COBOL modernization that nobody in the vendor pitch meetings wants to say out loud: the hard part isn't translating the syntax. The hard part is understanding what the code *means* when the only people who wrote it retired a decade ago.

I've been on the receiving end of this problem. Healthcare payers running billions of claims through programs that haven't been touched since the 90s. They can't find COBOL developers. They can't retire the systems. They're stuck.

So I built Cobalt: a CLI that reads legacy COBOL, assembles the hidden context that makes it comprehensible, and hands a modern developer the tools to understand, translate, and verify that code. No mainframe required. No IBM contract. Just the source files and a laptop.

## The "Paste It Into ChatGPT" Failure Mode

The first thing every team tries: dump the COBOL into an LLM and ask it to explain.

This fails, and it fails in a specific, predictable way. COBOL programs don't live in a single file. The data layouts live in *copybooks*: separate files that get included at compile time via `COPY` statements. The program you're looking at might reference `COPY CLAIMREC` and `COPY BENFTABL`, but the LLM can't see those files. It doesn't know what `CLM-BILLED-AMT` actually is.

Worse, it can't read the field declarations even if you paste them in. `PIC S9(7)V99 COMP-3` means "packed decimal, 7 integer digits and 2 fractional digits, stored in binary-coded decimal format." That `V` is an *implied* decimal point. It doesn't exist in storage. A naive model will either ignore it or misinterpret the scale.

This isn't a syntax problem. It's a context-assembly problem.

## Comprehension Is Context-Assembly, Not Syntax

That's the core insight behind Cobalt: **COBOL comprehension is a context-assembly problem, not a syntax problem.**

The value isn't in parsing the syntax (there are parsers for that). The value is in the engine that:

1. Resolves `COPY` statements to pull copybooks into a unified view
2. Decodes every `PIC` clause into a structured data dictionary with types and scales
3. Flags every `COMP-3` packed-decimal field and computes its exact Java equivalent
4. Maps the `PERFORM` paragraph structure into a call graph
5. Annotates `REDEFINES`, `88`-level conditions, and `OCCURS` arrays

Then, and only then, hands the assembled context to an LLM. The model doesn't have to guess what `PIC S9(7)V99 COMP-3` means. It's told: `BigDecimal(scale=2)`. That answer is computed by code, pinned by tests, and non-negotiable.

## Walking the Build

The architecture has two layers: deterministic and probabilistic.

The deterministic layer is a Java parser (a thin wrapper around ProLeap/ANTLR4) that emits a JSON schema, plus a Python context assembler that reads that schema and builds the grounded program model. This layer resolves copybooks, computes PIC-to-type mappings, flags COMP-3 fields, and builds the paragraph dependency graph. Zero LLM calls. Zero ambiguity.

```
SOURCE.cbl + copy/*.cpy
  → ProLeap parser (Java, subprocess) → JSON schema
  → Context assembler (Python) → data dictionary + PERFORM graph + semantics rules
  → LLM (Claude via LiteLLM) → explain / translate / test
```

The probabilistic layer is the LLM, constrained by the deterministic context. It writes the English explanation, the Java translation, and the characterization tests. It can still make mistakes in *logic*. But it can never misread a packed decimal, because that decision was made before it saw the code.

## The COMP-3 Money-Corruption Story

This is the part that keeps me up at night, and the reason the deterministic layer exists.

`COMP-3` (packed decimal) is how COBOL stores monetary values. Two digits per byte, with the sign in the last nibble. The dollar amount `$1234.56` stored in a `PIC S9(7)V99 COMP-3` field occupies 5 bytes: `01 23 45 67 0C`. The implied decimal (`V99`) means the last two digits are cents. No floating point. No rounding surprises. Exact.

Now watch what happens when a naive translator converts this to Java using `double`:

```java
// WRONG: what naive LLM translation produces
double billedAmt = 1234.56;
double allowedAmt = billedAmt * 0.80;
// allowedAmt = 987.6480000000001 (IEEE 754 noise)
```

In COBOL, that same arithmetic with truncation semantics (no `ROUNDED` keyword) produces `987.64`. Not `987.65` (rounded). Not `987.648` (extended). The result is truncated to the receiving field's scale. Period.

Run a few thousand claims through a float-based translation and the accumulated error is real money. In healthcare: incorrectly adjudicated claims. In banking: failed audits.

Cobalt's fix is structural. The context assembler computes the correct representation and the translation is constrained to it:

```java
// CORRECT: what Cobalt's constrained translation produces
BigDecimal billedAmt = new BigDecimal("1234.56");
BigDecimal allowedAmt = billedAmt.multiply(new BigDecimal("0.80"))
    .setScale(2, RoundingMode.DOWN);  // COBOL truncates, not rounds
// allowedAmt = 987.64 (exact, matches GnuCOBOL golden master)
```

The model doesn't *choose* to use `BigDecimal`. It's told to. The scale isn't inferred. It's computed from the PIC clause. The rounding mode isn't guessed. It's determined by whether `ROUNDED` appears in the COBOL source.

## Verifying Without a Mainframe

Translations need verification. But you can't run the original COBOL without a mainframe. Or can you?

GnuCOBOL is an open-source COBOL compiler for Linux. It compiles COBOL to C, then to native binaries. Cobalt ships a sample healthcare claims program (`claimcalc.cbl`) with a committed golden master: the verbatim stdout of that program compiled and run under GnuCOBOL 3.1.2.

The golden master is the source of truth. Every number in it was computed by actual COBOL arithmetic:

```
CLAIM: CLM0000002  PLAN: PPO  TYPE: MD  STATUS: ADJUDICATED
  BILLED:         1234.56
  ALLOWED:         987.64
  DEDUCTIBLE:        0.00
  COINSURANCE:     197.52
  PLAN PAID:       790.12
  MEMBER RESP:     444.44
```

That `987.64` (not `.65`) is the truncation story in action. And `197.52` (not `.53`) is the same truncation applied again: `987.64 × 0.20 = 197.528`, truncated to `197.52`. Cobalt's test suite re-derives every one of these numbers with exact `BigDecimal` arithmetic.

## The Demo

Three commands on the bundled sample. Real output.

**Inspect** (zero LLM calls, shows the assembled context):

```
$ cobalt inspect assets/samples/claimcalc.cbl -I assets/samples/copy

PROGRAM: CLAIMCALC  (source: claimcalc.cbl, parsed by: proleap)

=== DATA DICTIONARY (copybooks inlined, PIC decoded) ===
NAME                         LVL PICTURE      USAGE    JAVA TYPE
CLM-BILLED-AMT               5  S9(7)V99    COMP-3   BigDecimal(scale=2)
CLM-ALLOWED-AMT              5  S9(7)V99    COMP-3   BigDecimal(scale=2)
CLM-COINS-AMT                5  S9(7)V99    COMP-3   BigDecimal(scale=2)
...

=== PERFORM graph ===
0000-MAIN
  1000-INIT
  2000-PROCESS-ONE-CLAIM
    2100-LOAD-CLAIM
    2200-FIND-PLAN
    2300-CALC-ALLOWED
    2400-APPLY-DEDUCTIBLE
    2500-APPLY-COST-SHARE
  8000-PRINT-TOTALS
  9000-TERM
```

**Explain** (one LLM call, grounded by the assembled context):

```
$ cobalt explain assets/samples/claimcalc.cbl -I assets/samples/copy
```

Produces a structured explanation: what the program does, what each data structure means in business terms, the encoded business rules (including truncation semantics), and the paragraph control flow.

**Translate** (one LLM call, constrained by the data dictionary):

```
$ cobalt translate assets/samples/claimcalc.cbl -I assets/samples/copy --to java
```

Produces idiomatic Java 17 with `BigDecimal` data classes, correct scales, and `RoundingMode.DOWN` for every arithmetic operation that COBOL truncates.

## What Cobalt Is NOT

Let me be honest about scope.

- **Not a compiler.** The LLM writes the logic. It can be wrong. Every output needs human review.
- **Not a mainframe migration suite.** No CICS, no embedded SQL, no VSAM, no JCL. Batch-style computational COBOL only.
- **Not z/OS-verified.** The golden master comes from GnuCOBOL on Linux. IBM Enterprise COBOL differs in edge cases.
- **Not benchmarked.** The test suite mocks the LLM provider. Real-model quality: not measured.
- **Not magic.** Translations are a starting point for human review, not a production deployment.

## Getting Started

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/cobol-agent && pip install -e .

export COBALT_MODEL=anthropic/claude-sonnet-4-6   # any LiteLLM model string
cobalt explain assets/samples/claimcalc.cbl -I assets/samples/copy
```

No API key yet? `cobalt inspect` runs the full parse/assembly pipeline with zero API calls. You can see exactly what context the model would receive without spending a token.

## What's Next

The roadmap is clear: `--to python` translation target, batch mode over whole codebases, and CICS/DB2 awareness (detection and honest refusal first, translation later). The parser handles COBOL-85 standard today. IBM dialect extensions and z/OS golden masters come when licensing permits.

The bigger bet is the architecture. Every COBOL modernization effort I've seen fail started by letting the model guess at data semantics. Cobalt inverts that: compute the semantics deterministically, then constrain the model to them. The model writes logic. Code decides what the data means.

That's a pattern that generalizes well beyond COBOL.

---

*Cobalt is source-available under the Elastic License 2.0 (you may use, modify, and self-host it, but not offer it to third parties as a hosted or managed service). Built on [ProLeap COBOL Parser](https://github.com/uwol/proleap-cobol-parser) (Apache-2.0), [GnuCOBOL](https://gnucobol.sourceforge.io/), and [LiteLLM](https://github.com/BerriAI/litellm).*
