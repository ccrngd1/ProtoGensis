# Status: pseudoact

## Current State: ✅ COMPLETE (v1.1 — fixes applied)

## Timeline
- 2026-03-09 21:13 UTC — Project scaffolded
- 2026-03-09 21:21 UTC — Initial build complete, 55/55 tests passing
- 2026-03-13 23:46 UTC — Fix request received (request-pseudoact-fixes.json)
- 2026-03-13 23:47 UTC — All fixes applied, 55/55 tests passing

## Fixes Applied (2026-03-13)
### Critical (P0)
- `tools.py` — Replaced unsafe `eval()` with AST-based safe math parser
- `executor.py` — Variable substitution now uses regex word boundaries (no more substring corruption)
- `parser.py` — While loops now default to max_iterations=100 (was returning None → failure)
- `executor.py` — Method calls: updated system prompt to use list concatenation vs unsupported append()
- `synthesizer.py` / `executor.py` — Bedrock API failures now caught, logged, return descriptive error
- `executor.py` — Tool execution failures stored as step error result; execution continues

### High (P1)
- `executor.py` — Arithmetic expressions (i + 1, count * 2) now evaluated via safe AST parser
- `executor.py` — Loop variables (for i in range()) now bound in context per iteration

### Documentation + Infrastructure
- `README.md` — Method calls marked unsupported in v0.1; venv instructions added; examples verified
- `run.sh` (NEW) — Executable venv setup + demo runner

## Test Results
- **55/55 passing** (unchanged count, no regressions)

## Blockers
None

---
*Updated: 2026-03-13 23:47 UTC*
